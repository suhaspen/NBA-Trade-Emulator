"""
Parse Basketball-Reference ``contracts/players.html`` table and merge into players.csv.

Respect Sports Reference Terms of Service; use for personal/educational purposes only.
"""

from __future__ import annotations

import re
import unicodedata
from io import StringIO
from pathlib import Path

import pandas as pd

from season_utils import nba_season_id


def normalize_name(name: str) -> str:
    if not isinstance(name, str):
        return ""
    nfkd = unicodedata.normalize("NFKD", name)
    ascii_name = nfkd.encode("ascii", "ignore").decode("ascii")
    return re.sub(r"[^a-z ]", "", ascii_name.lower()).strip()


def parse_bref_contracts_dataframe(
    df: pd.DataFrame,
    season_id: str | None = None,
) -> pd.DataFrame:
    """
    BRef player_contracts table → name_key, salary_2023_24 (misnamed: current year cap hit),
    contract_years_remaining, optional team from ``Tm``.
    """
    season_id = season_id or nba_season_id()
    if df.empty:
        return pd.DataFrame()

    df = df.copy()
    if isinstance(df.columns, pd.MultiIndex):
        df.columns = [" ".join(str(c) for c in col if str(c) != "nan").strip() for col in df.columns]
    df.columns = [str(c).strip().replace("\xa0", " ") for c in df.columns]

    player_col = next(
        (c for c in df.columns if "player" in c.lower() or c.lower() == "name"),
        None,
    )
    if not player_col:
        return pd.DataFrame()

    df = df[df[player_col].notna()].copy()
    df[player_col] = df[player_col].astype(str).str.strip()
    df = df[~df[player_col].str.match(r"^(Player|Rk|nan)$", case=False)].copy()

    sal_cols = [
        c
        for c in df.columns
        if re.search(r"20[0-9]{2}-[0-9]{2}", str(c)) or re.search(r"20[0-9]{2}\s*-\s*[0-9]{2}", str(c))
    ]
    sal_cols = list(dict.fromkeys(sal_cols))

    def clean_sal(v):
        if pd.isna(v):
            return None
        s = str(v).replace("$", "").replace(",", "").strip()
        if s in ("", "--", "2-Way", "nan"):
            return None
        try:
            return float(s)
        except ValueError:
            return None

    # Current season salary column: prefer header containing season_id (e.g. 2025-26)
    cur_col = None
    for c in sal_cols:
        if season_id in str(c):
            cur_col = c
            break
    if cur_col is None and sal_cols:
        cur_col = sal_cols[0]

    result = pd.DataFrame({"player_name_sal": df[player_col]})
    team_col = next((c for c in df.columns if c in ("Tm", "Team")), None)
    if team_col:
        result["team_sal"] = df[team_col].astype(str).str.strip().str.upper()

    if sal_cols and cur_col:
        result["salary_2023_24"] = df[cur_col].apply(clean_sal)
        result["contract_years_remaining"] = df[sal_cols].apply(
            lambda row: sum(1 for c in sal_cols if clean_sal(row.get(c)) is not None),
            axis=1,
        )
    else:
        result["salary_2023_24"] = None
        result["contract_years_remaining"] = 0

    result["name_key"] = result["player_name_sal"].apply(normalize_name)
    # De-dupe: prefer row with max current salary (two-way / duplicate noise)
    result = result.sort_values("salary_2023_24", ascending=False, na_position="last")
    if "team_sal" in result.columns:
        result = result.drop_duplicates(subset=["name_key", "team_sal"], keep="first")
    else:
        result = result.drop_duplicates(subset=["name_key"], keep="first")
    return result.reset_index(drop=True)


def merge_salaries_into_players(
    players: pd.DataFrame,
    sal: pd.DataFrame,
) -> pd.DataFrame:
    """Left-merge contract rows onto stats rows. Team match first, then name-only fallback."""
    out = players.copy()
    out["name_key"] = out["player_name"].apply(normalize_name)
    out["team_u"] = out["team"].astype(str).str.upper()
    out = out.drop(columns=["salary_2023_24", "contract_years_remaining"], errors="ignore")
    sal = sal.copy()
    cols = ["name_key", "salary_2023_24", "contract_years_remaining"]

    if "team_sal" in sal.columns:
        sal["team_sal"] = sal["team_sal"].astype(str).str.upper()
        sal_t = sal[
            ["name_key", "team_sal", "salary_2023_24", "contract_years_remaining"]
        ].drop_duplicates(subset=["name_key", "team_sal"], keep="first")
        merged = out.merge(
            sal_t,
            left_on=["name_key", "team_u"],
            right_on=["name_key", "team_sal"],
            how="left",
        )
        sal_n = sal.sort_values("salary_2023_24", ascending=False, na_position="last").drop_duplicates(
            "name_key", keep="first"
        )[cols].rename(
            columns={
                "salary_2023_24": "salary_2023_24_fb",
                "contract_years_remaining": "contract_years_remaining_fb",
            }
        )
        merged = merged.merge(sal_n[["name_key", "salary_2023_24_fb", "contract_years_remaining_fb"]], on="name_key", how="left")
        merged["salary_2023_24"] = merged["salary_2023_24"].fillna(merged["salary_2023_24_fb"])
        merged["contract_years_remaining"] = merged["contract_years_remaining"].fillna(
            merged["contract_years_remaining_fb"]
        )
        merged = merged.drop(
            columns=["salary_2023_24_fb", "contract_years_remaining_fb", "team_sal", "team_u", "name_key"],
            errors="ignore",
        )
    else:
        sal_u = sal.sort_values("salary_2023_24", ascending=False, na_position="last").drop_duplicates(
            "name_key", keep="first"
        )[cols]
        merged = out.merge(sal_u, on="name_key", how="left")
        merged = merged.drop(columns=["name_key", "team_u"], errors="ignore")

    merged["salary_2023_24"] = pd.to_numeric(merged["salary_2023_24"], errors="coerce")
    merged["contract_years_remaining"] = pd.to_numeric(
        merged["contract_years_remaining"], errors="coerce"
    ).fillna(0)
    return merged


def fetch_bref_contracts_html(url: str = "https://www.basketball-reference.com/contracts/players.html") -> str:
    """Download raw HTML (prefer curl_cffi TLS impersonation)."""
    last_err: Exception | None = None
    try:
        from curl_cffi import requests as curl_requests

        r = curl_requests.get(url, impersonate="chrome131", timeout=90)
        if r.status_code == 200:
            return r.text
        last_err = RuntimeError(f"curl_cffi HTTP {r.status_code}")
    except ImportError:
        last_err = ImportError("curl_cffi not installed")
    except Exception as e:
        last_err = e

    import requests

    headers = {
        "User-Agent": (
            "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
            "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36"
        ),
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
        "Accept-Language": "en-US,en;q=0.9",
        "Referer": "https://www.basketball-reference.com/",
    }
    r = requests.get(url, headers=headers, timeout=90)
    if r.status_code != 200:
        raise RuntimeError(
            f"Could not fetch contracts ({r.status_code}). "
            f"Install curl_cffi (pip install curl-cffi) for better compatibility. "
            f"Previous error: {last_err}"
        ) from last_err
    return r.text


def contracts_html_to_dataframe(html: str) -> pd.DataFrame:
    html = html.replace("<!--", "").replace("-->", "")
    for parser in ("lxml", "html.parser"):
        try:
            tables = pd.read_html(StringIO(html), flavor=parser)
        except ValueError:
            continue
        for t in tables:
            flat = " ".join(str(c) for col in t.columns for c in (col if isinstance(col, tuple) else (col,)))
            if "player" in flat.lower() and re.search(r"20[0-9]{2}-[0-9]{2}", flat):
                return t
        if tables:
            return max(tables, key=lambda x: x.shape[0] * max(x.shape[1], 1))
    return pd.DataFrame()


def merge_file(
    players_path: str | Path,
    out_path: str | Path | None = None,
    season_id: str | None = None,
) -> Path:
    """Fetch BRef contracts, merge into players CSV, write."""
    season_id = season_id or nba_season_id()
    players_path = Path(players_path)
    out_path = Path(out_path) if out_path else players_path

    html = fetch_bref_contracts_html()
    raw = contracts_html_to_dataframe(html)
    if raw.empty:
        raise RuntimeError("No player_contracts table parsed — site layout change or empty response.")

    sal = parse_bref_contracts_dataframe(raw, season_id=season_id)
    if sal.empty:
        raise RuntimeError("Parsed contracts table was empty.")

    players = pd.read_csv(players_path)
    merged = merge_salaries_into_players(players, sal)
    merged.to_csv(out_path, index=False)

    n_hit = merged["salary_2023_24"].notna().sum()
    print(f"Merged salaries: {n_hit}/{len(merged)} rows with salary (season column ~{season_id})")
    print(f"Wrote {out_path.resolve()}")
    return out_path
