
"""
Alternate data source (if this script gets HTTP 403 from Sports Reference):

  python fetch_nba_league_stats.py

Writes the same ``data/players.csv`` path the web app expects (salaries blank there).
"""

import sys, time, subprocess
from pathlib import Path
import pandas as pd
import requests
from io import StringIO
import unicodedata, re

# ── 0. Install parsing libraries ──────────────────────────────────────────────
for lib in ["lxml", "html5lib", "beautifulsoup4"]:
    subprocess.run(
        [sys.executable, "-m", "pip", "install", lib, "--target=/tmp/site-packages", "-q"],
        capture_output=True
    )
if "/tmp/site-packages" not in sys.path:
    sys.path.insert(0, "/tmp/site-packages")

BREF_SEASON = 2024  # Basketball-Reference uses end-year of season

# ── 1. All 30 teams — Basketball-Reference `Tm` codes (note: BRK, CHO, PHO, etc.) ──
TARGET_TEAMS_BREF = {
    "ATL",
    "BOS",
    "BRK",
    "CHI",
    "CHO",
    "CLE",
    "DAL",
    "DEN",
    "DET",
    "GSW",
    "HOU",
    "IND",
    "LAC",
    "LAL",
    "MEM",
    "MIA",
    "MIL",
    "MIN",
    "NOP",
    "NYK",
    "OKC",
    "ORL",
    "PHI",
    "PHO",
    "POR",
    "SAC",
    "SAS",
    "TOR",
    "UTA",
    "WAS",
}
assert len(TARGET_TEAMS_BREF) == 30, f"Expected 30 teams, got {len(TARGET_TEAMS_BREF)}"
print(f"Target teams ({len(TARGET_TEAMS_BREF)}): {sorted(TARGET_TEAMS_BREF)}")

# Browser-like defaults — bare requests often get HTTP 403 from Sports Reference / CDN.
BREF_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
        "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36"
    ),
    "Accept": (
        "text/html,application/xhtml+xml,application/xml;q=0.9,"
        "image/avif,image/webp,image/apng,*/*;q=0.8"
    ),
    "Accept-Language": "en-US,en;q=0.9",
    "Accept-Encoding": "gzip, deflate, br",
    "Connection": "keep-alive",
    "Upgrade-Insecure-Requests": "1",
    "Sec-Fetch-Dest": "document",
    "Sec-Fetch-Mode": "navigate",
    "Sec-Fetch-Site": "none",
    "Sec-Fetch-User": "?1",
    "sec-ch-ua": '"Google Chrome";v="131", "Chromium";v="131", "Not_A Brand";v="24"',
    "sec-ch-ua-mobile": "?0",
    "sec-ch-ua-platform": '"macOS"',
}


def make_bref_session() -> requests.Session:
    s = requests.Session()
    s.headers.update(BREF_HEADERS)
    return s


def bref_warmup(session: requests.Session) -> None:
    """Hit the homepage first so CDN / WAF sees a normal entry path."""
    try:
        r = session.get("https://www.basketball-reference.com/", timeout=60)
        if r.status_code == 403:
            print("  Warmup: still HTTP 403 (site may be blocking automated access from this network).")
        elif r.status_code != 200:
            print(f"  Warmup: HTTP {r.status_code}")
        else:
            print("  Warmup: OK (session cookies / referer chain established)")
        time.sleep(2)
    except Exception as e:
        print(f"  Warmup error (continuing anyway): {e}")
BREF_SESSION = make_bref_session()
bref_warmup(BREF_SESSION)

def normalize_name(name):
    if not isinstance(name, str):
        return ""
    nfkd = unicodedata.normalize("NFKD", name)
    ascii_name = nfkd.encode("ascii", "ignore").decode("ascii")
    return re.sub(r"[^a-z ]", "", ascii_name.lower()).strip()

def fetch_bref_table(
    session: requests.Session,
    url: str,
    table_id: str,
    sleep_sec: float = 5,
    retries: int = 3,
):
    """Scrape Basketball-Reference table, handling comment-hidden tables."""
    # Subpage navigation: looks like we came from the site index.
    sub_headers = {
        "Referer": "https://www.basketball-reference.com/",
        "Sec-Fetch-Site": "same-origin",
    }
    for attempt in range(retries):
        time.sleep(sleep_sec + attempt * 4)
        try:
            resp = session.get(url, headers=sub_headers, timeout=60)
            if resp.status_code == 429:
                print(f"  Rate limited (429), waiting 30s...")
                time.sleep(30)
                continue
            if resp.status_code == 403:
                print(
                    f"  HTTP 403 Forbidden — Sports Reference often blocks scripts. "
                    f"Try again from home Wi‑Fi, increase sleeps, or export CSV manually from the site. "
                    f"(Attempt {attempt + 1}/{retries})"
                )
                continue
            if resp.status_code != 200:
                print(f"  HTTP {resp.status_code}")
                continue
            # Strip HTML comments (bref hides some tables)
            html = resp.text.replace("<!--", "").replace("-->", "")
            # Try lxml first, fall back to html.parser
            for parser in ["lxml", "html.parser"]:
                tables = pd.read_html(StringIO(html), attrs={"id": table_id}, flavor=parser)
                if tables:
                    print(f"  [{table_id}] {tables[0].shape} via {parser}")
                    return tables[0]
        except Exception as e:
            print(f"  Attempt {attempt+1} error: {e}")
    print(f"  FAILED: {table_id}")
    return pd.DataFrame()

# ── 2. Fetch three tables from Basketball Reference ───────────────────────────
print("\n=== Fetching per-game stats ===")
raw_pg = fetch_bref_table(
    BREF_SESSION,
    f"https://www.basketball-reference.com/leagues/NBA_{BREF_SEASON}_per_game.html",
    "per_game_stats",
)
print(f"  Columns: {list(raw_pg.columns[:10]) if not raw_pg.empty else 'empty'}")

print("\n=== Fetching advanced stats ===")
raw_adv = fetch_bref_table(
    BREF_SESSION,
    f"https://www.basketball-reference.com/leagues/NBA_{BREF_SEASON}_advanced.html",
    "advanced",
)
print(f"  Columns: {list(raw_adv.columns[:10]) if not raw_adv.empty else 'empty'}")

print("\n=== Fetching salary data ===")
raw_sal = fetch_bref_table(
    BREF_SESSION,
    "https://www.basketball-reference.com/contracts/players.html",
    "player_contracts",
    sleep_sec=6,
)
print(f"  Columns: {list(raw_sal.columns[:10]) if not raw_sal.empty else 'empty'}")

# ── 3. Detect team column name ────────────────────────────────────────────────
def get_team_col(df):
    """Find team column regardless of whether it's 'Tm' or 'Team'."""
    for c in ["Tm", "Team"]:
        if c in df.columns:
            return c
    return None

# ── 4. Process per-game stats ────────────────────────────────────────────────
def process_per_game(df, target_teams):
    if df.empty:
        return pd.DataFrame()
    df = df.copy()

    # Detect player/team column names
    player_col = "Player" if "Player" in df.columns else None
    team_col   = get_team_col(df)

    if not player_col:
        print("  No 'Player' column found!")
        return pd.DataFrame()

    # Remove repeated header rows
    df = df[df[player_col].astype(str) != player_col].copy()
    df = df[df[player_col].notna()].copy()

    # Handle traded players: keep stats-aggregated row but use last team
    if team_col:
        tot_mask = df[team_col].astype(str) == "TOT"
        non_tot  = df[~tot_mask].copy()
        last_team = non_tot.groupby(player_col)[team_col].last().rename("last_team")

        # Sort: TOT rows sort later alphabetically; drop_duplicates keeps last
        pg_dedup = df.sort_values(team_col).drop_duplicates(subset=player_col, keep="last")
        pg_dedup = pg_dedup.merge(last_team.reset_index(), on=player_col, how="left")
        pg_dedup[team_col] = pg_dedup["last_team"].fillna(pg_dedup[team_col])
        pg_dedup.drop(columns=["last_team"], inplace=True)
    else:
        pg_dedup = df.drop_duplicates(subset=player_col).copy()

    # Filter to target teams
    if team_col:
        pg_dedup = pg_dedup[pg_dedup[team_col].isin(target_teams)].copy()

    # Column mapping
    col_map = {
        player_col: "player_name",
        team_col: "team",
        "Age": "age", "G": "games_played", "GS": "games_started",
        "MP": "min_per_game",
        "FG%": "fg_pct", "3P%": "fg3_pct", "eFG%": "efg_pct", "FT%": "ft_pct",
        "PTS": "pts", "AST": "ast", "TRB": "reb",
        "STL": "stl", "BLK": "blk", "TOV": "tov", "PF": "pf",
        "ORB": "orb", "DRB": "drb",
    }
    col_map = {k: v for k, v in col_map.items() if k and k in pg_dedup.columns}
    pg_out = pg_dedup[list(col_map.keys())].rename(columns=col_map).copy()

    # Numeric conversion
    for col in ["age", "games_played", "games_started", "min_per_game",
                "fg_pct", "fg3_pct", "efg_pct", "ft_pct",
                "pts", "ast", "reb", "stl", "blk", "tov", "pf", "orb", "drb"]:
        if col in pg_out.columns:
            pg_out[col] = pd.to_numeric(pg_out[col], errors="coerce")

    # Games missed proxy
    if "games_played" in pg_out.columns:
        pg_out["games_missed"] = 82 - pg_out["games_played"].fillna(0)

    return pg_out.reset_index(drop=True)

pg_clean = process_per_game(raw_pg, TARGET_TEAMS_BREF)
print(f"\npg_clean: {pg_clean.shape}")
if not pg_clean.empty and "team" in pg_clean.columns:
    print(f"Teams: {sorted(pg_clean['team'].unique())}")

# ── 5. Process advanced stats ────────────────────────────────────────────────
def process_advanced(df):
    if df.empty:
        return pd.DataFrame()
    df = df.copy()
    player_col = "Player" if "Player" in df.columns else None
    team_col   = get_team_col(df)

    if not player_col:
        return pd.DataFrame()

    # Remove header rows
    df = df[df[player_col].astype(str) != player_col].copy()
    df = df[df[player_col].notna()].copy()

    # Handle traded players: keep TOT row
    if team_col:
        df = df.sort_values(team_col).drop_duplicates(subset=player_col, keep="last")

    # Map columns
    col_map = {
        player_col: "player_name_adv",
        "BPM": "bpm", "VORP": "vorp",
        "WS": "ws", "WS/48": "ws_per_48",
        "OWS": "ows", "DWS": "dws",
        "PER": "per",
        "USG%": "usg_pct", "TS%": "ts_pct",
        "ORtg": "off_rating", "DRtg": "def_rating",
        "+/-": "plus_minus",
        "OBPM": "obpm", "DBPM": "dbpm",
    }
    col_map = {k: v for k, v in col_map.items() if k in df.columns}
    adv_out = df[list(col_map.keys())].rename(columns=col_map).copy()

    for col in ["bpm", "vorp", "ws", "ws_per_48", "ows", "dws",
                "per", "usg_pct", "ts_pct", "off_rating", "def_rating",
                "plus_minus", "obpm", "dbpm"]:
        if col in adv_out.columns:
            adv_out[col] = pd.to_numeric(adv_out[col], errors="coerce")

    adv_out["name_key"] = adv_out["player_name_adv"].apply(normalize_name)
    return adv_out.reset_index(drop=True)

adv_clean = process_advanced(raw_adv)
print(f"adv_clean: {adv_clean.shape}")

# ── 6. Process salary data ────────────────────────────────────────────────────
def process_salary(df):
    if df.empty:
        return pd.DataFrame()
    df = df.copy()

    # Flatten MultiIndex columns if present
    if isinstance(df.columns, pd.MultiIndex):
        df.columns = [" ".join(str(c) for c in col if str(c) != "nan").strip()
                      for col in df.columns]
    df.columns = [str(c).strip().replace("\xa0", " ") for c in df.columns]
    print(f"  Salary columns: {list(df.columns)}")

    # Find player name column
    player_col = next(
        (c for c in df.columns if "player" in c.lower() or c.lower() == "name"),
        None
    )
    if not player_col:
        print("  No player column found in salary data")
        return pd.DataFrame()

    df = df[df[player_col].notna()].copy()
    df[player_col] = df[player_col].astype(str).str.strip()
    df = df[~df[player_col].str.match(r"^(Player|Rk|nan)$")].copy()

    # Identify salary year columns
    year_pats = ["2023-24", "2024-25", "2025-26", "2026-27", "2027-28", "2028-29", "2029-30"]
    sal_cols = [c for c in df.columns if any(p in str(c) for p in year_pats)]
    print(f"  Salary year cols: {sal_cols}")

    def clean_sal(v):
        if pd.isna(v): return None
        s = str(v).replace("$", "").replace(",", "").strip()
        if s in ("", "--", "2-Way", "nan"): return None
        try: return float(s)
        except: return None

    result = pd.DataFrame({"player_name_sal": df[player_col]})

    if sal_cols:
        cur_col = next((c for c in sal_cols if "2023-24" in str(c)), sal_cols[0])
        result["salary_2023_24"] = df[cur_col].apply(clean_sal)
        future = [c for c in sal_cols if "2023-24" not in str(c)]
        if future:
            result["contract_years_remaining"] = df[future].apply(
                lambda row: sum(1 for v in row if clean_sal(v) is not None), axis=1
            )
        else:
            result["contract_years_remaining"] = 0
    else:
        result["salary_2023_24"] = None
        result["contract_years_remaining"] = 0

    result["name_key"] = result["player_name_sal"].apply(normalize_name)
    return result.drop_duplicates(subset="name_key").reset_index(drop=True)

sal_clean = process_salary(raw_sal)
print(f"sal_clean: {sal_clean.shape}")

# ── 7. Merge all three datasets ───────────────────────────────────────────────
print("\n=== Merging datasets ===")

if pg_clean.empty:
    raise RuntimeError(
        "Per-game data is empty - cannot proceed with merge. "
        "Basketball-Reference may be blocking requests (HTTP 403). "
        "Use the NBA Stats feed instead:  python fetch_nba_league_stats.py"
    )

pg_clean["name_key"] = pg_clean["player_name"].apply(normalize_name)

# Merge advanced stats
if not adv_clean.empty:
    adv_merge = adv_clean.drop(columns=["player_name_adv"], errors="ignore")
    merged_df = pg_clean.merge(adv_merge, on="name_key", how="left")
    print(f"  After adv merge: {merged_df.shape}")
else:
    merged_df = pg_clean.copy()
    for col in ["bpm", "vorp", "ws", "ws_per_48", "plus_minus"]:
        merged_df[col] = None
    print("  BRef advanced: empty, added null columns")

# Merge salary
if not sal_clean.empty:
    sal_merge = sal_clean.drop(columns=["player_name_sal"], errors="ignore")
    merged_df = merged_df.merge(sal_merge, on="name_key", how="left")
    print(f"  After salary merge: {merged_df.shape}")
else:
    merged_df["salary_2023_24"] = None
    merged_df["contract_years_remaining"] = 0
    print("  Salary: empty, added null columns")

# Cleanup
merged_df.drop(columns=["name_key"], errors="ignore", inplace=True)

# Ensure plus_minus exists
if "plus_minus" not in merged_df.columns:
    merged_df["plus_minus"] = None

# Final numeric conversion pass
num_cols = ["age", "games_played", "games_started", "min_per_game",
            "fg_pct", "fg3_pct", "efg_pct", "ft_pct", "pts", "ast", "reb",
            "stl", "blk", "tov", "pf", "orb", "drb", "games_missed",
            "bpm", "vorp", "ws", "ws_per_48", "ows", "dws",
            "per", "usg_pct", "ts_pct", "off_rating", "def_rating",
            "plus_minus", "obpm", "dbpm", "salary_2023_24", "contract_years_remaining"]
for col in num_cols:
    if col in merged_df.columns:
        merged_df[col] = pd.to_numeric(merged_df[col], errors="coerce")

merged_df.sort_values(["team", "pts"], ascending=[True, False], inplace=True)
merged_df.reset_index(drop=True, inplace=True)

# ── 8. Final report ───────────────────────────────────────────────────────────
print(f"\n{'='*60}")
print(f"FINAL merged_df shape: {merged_df.shape}")
print(f"\nColumns ({len(merged_df.columns)}):")
print(list(merged_df.columns))

print(f"\nTeam player counts:")
print(merged_df.groupby("team").size().to_string())

print(f"\nNull counts (key columns):")
key_cols = ["pts", "ast", "reb", "fg_pct", "fg3_pct", "plus_minus",
            "bpm", "vorp", "salary_2023_24", "contract_years_remaining",
            "age", "games_missed"]
for col in key_cols:
    if col in merged_df.columns:
        n   = merged_df[col].isna().sum()
        pct = 100 * n / len(merged_df)
        print(f"  {col:25s}: {n:3d} nulls ({pct:.0f}%)")

print(f"\nSample rows (first 10):")
sample_cols = ["player_name", "team", "age", "pts", "ast", "reb",
               "fg_pct", "fg3_pct", "plus_minus", "bpm", "vorp",
               "salary_2023_24", "contract_years_remaining", "games_missed"]
sample_cols = [c for c in sample_cols if c in merged_df.columns]
pd.set_option("display.max_columns", None)
pd.set_option("display.width", 220)
print(merged_df[sample_cols].head(10).to_string(index=False))

# Uncomment to refresh the web app player pool (see data/players.csv + TRADE_EMULATOR_DATA):
# out = Path(__file__).resolve().parent / "data" / "players.csv"
# out.parent.mkdir(parents=True, exist_ok=True)
# merged_df.to_csv(out, index=False)
# print(f"\nWrote {out}")
