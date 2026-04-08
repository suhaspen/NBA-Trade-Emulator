from __future__ import annotations

import os
import re
import unicodedata
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd

from cba_rules import get_band, side_is_legal
from picks import PICK_CATALOG, resolve_pick

# Distinct series colors for charts (high contrast, color-blind friendly lean).
CHART_PALETTE = [
    "#2563eb",
    "#ea580c",
    "#ca8a04",
    "#16a34a",
    "#9333ea",
    "#db2777",
]
PACKAGE_COLOR_A = "#0891b2"
PACKAGE_COLOR_B = "#4f46e5"

RADAR_LABELS = [
    "Scoring",
    "Playmaking",
    "Defense",
    "Efficiency",
    "Contract value",
    "Longevity",
]


def normalize_name(name: str) -> str:
    if not isinstance(name, str):
        return ""
    nfkd = unicodedata.normalize("NFKD", name)
    ascii_name = nfkd.encode("ascii", "ignore").decode("ascii")
    return re.sub(r"[^a-z ]", "", ascii_name.lower()).strip()


def _safe_series(df: pd.DataFrame, col: str, default: float = 0.0) -> pd.Series:
    if col in df.columns:
        return pd.to_numeric(df[col], errors="coerce").fillna(default)
    return pd.Series(default, index=df.index)


def ml_scores_csv_path() -> Path:
    env = os.environ.get("TRADE_EMULATOR_ML_SCORES")
    return Path(env).resolve() if env else (Path(__file__).resolve().parent / "data" / "ml_player_scores.csv")


def load_ml_score_lookup() -> pd.DataFrame | None:
    """Offline-trained scores keyed by player_id; None if file missing."""
    path = ml_scores_csv_path()
    if not path.is_file():
        return None
    m = pd.read_csv(path)
    if "player_id" not in m.columns:
        return None
    m = m.copy()
    m["player_id"] = pd.to_numeric(m["player_id"], errors="coerce").astype("Int64")
    m = m.dropna(subset=["player_id"])
    m["player_id"] = m["player_id"].astype(int)
    keep = ["player_id", "ml_vorp_predicted", "ml_value_score"]
    for c in keep:
        if c not in m.columns:
            return None
    return m[keep]


def enrich_player_pool(raw: pd.DataFrame) -> pd.DataFrame:
    """Add salary_mm, health, age curve, contract_efficiency, trade_value_score."""
    df = raw.copy()

    sal = _safe_series(df, "salary_2023_24")
    df["salary_mm"] = sal / 1_000_000.0
    df["salary_mm"] = df["salary_mm"].fillna(0.0)

    gp = _safe_series(df, "games_played", 0.0)
    df["health_score"] = (gp / 82.0).clip(0, 1)

    age = _safe_series(df, "age", 26.0)
    df["age_multiplier"] = np.clip(1.15 - (age - 22) * 0.018, 0.55, 1.15)

    yrs = _safe_series(df, "contract_years_remaining", 1.0)
    tv_proxy = _safe_series(df, "bpm") * 2.5 + _safe_series(df, "vorp") * 5.0
    sal_m = df["salary_mm"].replace(0, np.nan)
    eff = (tv_proxy / sal_m).replace([np.inf, -np.inf], np.nan)
    med = float(eff.median(skipna=True) or 1.0)
    ce = eff.fillna(med).clip(0.05, 50.0)
    df["contract_efficiency"] = ce

    bpm = _safe_series(df, "bpm")
    vorp = _safe_series(df, "vorp")
    pts = _safe_series(df, "pts")
    ws = _safe_series(df, "ws")

    def _norm(s: pd.Series) -> pd.Series:
        lo, hi = float(s.min()), float(s.max())
        if hi - lo < 1e-9:
            return pd.Series(0.5, index=s.index)
        return (s - lo) / (hi - lo)

    # On-court “talent” vs contract / durability — reported separately + blended
    talent_comp = (
        0.38 * _norm(bpm)
        + 0.22 * _norm(vorp)
        + 0.22 * _norm(pts)
        + 0.18 * _norm(ws)
    )
    tmax = float(talent_comp.max()) or 1.0
    df["talent_score"] = (100.0 * talent_comp / tmax).clip(0, 100)

    long_raw = df["age_multiplier"] * df["health_score"]
    contract_comp = 0.55 * _norm(ce) + 0.45 * _norm(long_raw)
    cvm = float(contract_comp.max()) or 1.0
    df["contract_value_score"] = (100.0 * contract_comp / cvm).clip(0, 100)

    df["trade_value_score"] = (
        0.62 * df["talent_score"] + 0.38 * df["contract_value_score"]
    ).clip(0, 100)

    ml = load_ml_score_lookup()
    if ml is not None and "player_id" in df.columns:
        pid = pd.to_numeric(df["player_id"], errors="coerce")
        idx = ml.set_index("player_id")
        df["ml_vorp_predicted"] = pid.map(idx["ml_vorp_predicted"])
        df["ml_value_score"] = pid.map(idx["ml_value_score"])
    else:
        df["ml_vorp_predicted"] = np.nan
        df["ml_value_score"] = np.nan

    hv = 0.5 * df["trade_value_score"] + 0.5 * pd.to_numeric(df["ml_value_score"], errors="coerce")
    df["trade_value_hybrid"] = np.where(df["ml_value_score"].notna(), hv, df["trade_value_score"])

    for c in [
        "pts",
        "ast",
        "reb",
        "bpm",
        "vorp",
        "stl",
        "blk",
        "ts_pct",
        "dbpm",
        "obpm",
        "per",
        "ws",
    ]:
        if c not in df.columns:
            df[c] = 0.0
        else:
            df[c] = pd.to_numeric(df[c], errors="coerce").fillna(0.0)

    if "contract_years_remaining" not in df.columns:
        df["contract_years_remaining"] = 0
    else:
        df["contract_years_remaining"] = pd.to_numeric(
            df["contract_years_remaining"], errors="coerce"
        ).fillna(0)

    return df


def load_player_pool(csv_path: Path | str | None = None) -> pd.DataFrame:
    path = Path(csv_path) if csv_path else Path(__file__).resolve().parent / "data" / "players.csv"
    if not path.exists():
        raise FileNotFoundError(
            f"Player data not found at {path}. Add a CSV (see data/players.csv) or set TRADE_EMULATOR_DATA."
        )
    raw = pd.read_csv(path)
    if "player_name" not in raw.columns:
        raise ValueError("CSV must include player_name column")
    return enrich_player_pool(raw)


def find_player_row(
    pool: pd.DataFrame,
    query: str,
    team_hint: str | None = None,
    player_id: int | str | None = None,
) -> pd.Series:
    if player_id is not None and "player_id" in pool.columns:
        try:
            pid = int(player_id)
        except (TypeError, ValueError):
            pid = None
        if pid is not None:
            hit = pool.loc[pool["player_id"] == pid]
            if len(hit) == 1:
                return hit.iloc[0]
            if len(hit) > 1 and team_hint:
                tm = hit["team"].astype(str).str.upper() == team_hint.strip().upper()
                if tm.any():
                    return hit.loc[tm].iloc[0]

    q = (query or "").strip()
    if not q and not player_id:
        raise ValueError("Player query or player_id is required")
    if not q:
        raise ValueError(f"Player not found for player_id={player_id!r}")
    mask = pool["player_name"].astype(str).str.contains(re.escape(q), case=False, na=False, regex=True)
    if not mask.any():
        work = pool.copy()
        nk = normalize_name(q)
        work["_nk"] = work["player_name"].apply(normalize_name)
        mask = work["_nk"].str.contains(re.escape(nk), case=False, na=False, regex=True)
        sub = work.loc[mask].drop(columns=["_nk"], errors="ignore")
    else:
        sub = pool.loc[mask]
    if sub.empty:
        raise ValueError(f"Player not found: {query!r}")
    if team_hint and "team" in sub.columns:
        tm = sub["team"].astype(str).str.upper() == team_hint.strip().upper()
        if tm.any():
            sub = sub.loc[tm]
    return sub.iloc[0]


def _norm100(val: float, series: pd.Series) -> float:
    lo, hi = float(series.min()), float(series.max())
    if hi - lo < 1e-9:
        return 50.0
    return float(100.0 * (val - lo) / (hi - lo))


def radar_dimensions(player_row: pd.Series, pool: pd.DataFrame) -> list[float]:
    scoring = _norm100(float(player_row["pts"]), pool["pts"])
    playmaking = _norm100(float(player_row["ast"]), pool["ast"])
    defense = _norm100(float(player_row.get("dbpm", 0)), pool["dbpm"])
    efficiency = _norm100(float(player_row.get("ts_pct", 0)), pool["ts_pct"])
    contract_val = _norm100(float(player_row["contract_efficiency"]), pool["contract_efficiency"])
    longevity_raw = float(player_row["age_multiplier"]) * float(player_row["health_score"])
    pool_long = pool["age_multiplier"] * pool["health_score"]
    longevity = _norm100(longevity_raw, pool_long)
    return [scoring, playmaking, defense, efficiency, contract_val, longevity]


def _pick_candidates_by_value() -> list[dict[str, Any]]:
    rows = [
        {"id": k, "trade_value": float(v["trade_value"]), "label": v["label"]}
        for k, v in PICK_CATALOG.items()
    ]
    rows.sort(key=lambda x: -x["trade_value"])
    return rows


def _greedy_pick_labels(target_tv: float) -> list[str]:
    """Approximate pick bundle from catalog to cover a TV gap (illustrative)."""
    if target_tv <= 0:
        return []
    picks = _pick_candidates_by_value()
    chosen: list[str] = []
    remaining = float(target_tv)
    for p in picks:
        if remaining <= 0.5:
            break
        if float(p["trade_value"]) <= remaining + 5.0:
            chosen.append(p["label"])
            remaining -= float(p["trade_value"])
    if not chosen and picks:
        chosen.append(picks[0]["label"])
    return chosen[:4]


def build_balance_suggestions(
    label_a: str,
    label_b: str,
    sal_a: float,
    sal_b: float,
    ok_a: bool,
    ok_b: bool,
    max_a: float,
    max_b: float,
    tv_a: float,
    tv_b: float,
    bracket_a: str | None,
    bracket_b: str | None,
    tv_threshold: float = 5.0,
) -> list[dict[str, str]]:
    """
    Actionable (but simplified) ideas when salary or trade value is lopsided.
    Real trades need CBA nuance (apron, aggregating, STs, etc.).
    """
    out: list[dict[str, str]] = []
    surplus_a_vs_b = tv_a - tv_b
    ba = get_band(bracket_a)
    bb = get_band(bracket_b)

    if not ok_a:
        over = max(0.0, sal_a - max_a)
        min_incoming_b = (max(0.0, sal_a - ba.cushion_mm) / ba.multiplier) if sal_a > ba.cushion_mm else 0.0
        extra_b = max(0.0, min_incoming_b - sal_b)
        out.append(
            {
                "category": "salary",
                "title": f"{label_a} exceeds its aggregation band ({ba.short_label})",
                "detail": (
                    f"Preset uses up to ~{ba.multiplier:g}× incoming + ${ba.cushion_mm:.2f}M cushion. "
                    f"At ${sal_b:.1f}M incoming, max send ≈ ${max_a:.1f}M, but {label_a} sends ${sal_a:.1f}M (~${over:.1f}M over). "
                    f"Raise incoming by ~${extra_b:.1f}M, trim outgoing, add a TPE/ST exception in a real cap tool, or change apron preset."
                ),
            }
        )
    if not ok_b:
        over = max(0.0, sal_b - max_b)
        min_incoming_a = (max(0.0, sal_b - bb.cushion_mm) / bb.multiplier) if sal_b > bb.cushion_mm else 0.0
        extra_a = max(0.0, min_incoming_a - sal_a)
        out.append(
            {
                "category": "salary",
                "title": f"{label_b} exceeds its aggregation band ({bb.short_label})",
                "detail": (
                    f"Preset up to ~{bb.multiplier:g}× incoming + ${bb.cushion_mm:.2f}M. "
                    f"Over by ~${over:.1f}M; needs ~${extra_a:.1f}M more incoming from {label_a} or less outgoing."
                ),
            }
        )

    if surplus_a_vs_b > tv_threshold:
        bundle = _greedy_pick_labels(surplus_a_vs_b)
        pick_hint = ", ".join(bundle) if bundle else "a future first in your pick catalog"
        out.append(
            {
                "category": "value",
                "title": f"{label_a} is ahead by ~{surplus_a_vs_b:.1f} trade-value points",
                "detail": (
                    f"To tighten the gap without changing players, {label_b} could add draft assets worth roughly that margin "
                    f"(your presets suggest something like: {pick_hint}). Alternatively {label_a} could remove a pick or substitute a lower-value player."
                ),
            }
        )
    elif surplus_a_vs_b < -tv_threshold:
        gap = abs(surplus_a_vs_b)
        bundle = _greedy_pick_labels(gap)
        pick_hint = ", ".join(bundle) if bundle else "a future first in your pick catalog"
        out.append(
            {
                "category": "value",
                "title": f"{label_b} is ahead by ~{gap:.1f} trade-value points",
                "detail": (
                    f"{label_a} could add compensation such as: {pick_hint}, or {label_b} could drop picks / swap in a lower-impact contract player "
                    f"if salary rules allow."
                ),
            }
        )

    sal_gap = sal_a - sal_b
    if ok_a and ok_b and abs(sal_gap) > 15 and abs(surplus_a_vs_b) <= tv_threshold:
        out.append(
            {
                "category": "structure",
                "title": "Large salary imbalance but rule check passes",
                "detail": (
                    f"Salary differs by ~${abs(sal_gap):.1f}M. One side may want cash considerations (where allowed), pick swaps, or "
                    f"extra minimum deals to align incentives even when aggregation math works on paper."
                ),
            }
        )

    if not out and ok_a and ok_b and abs(surplus_a_vs_b) <= tv_threshold:
        out.append(
            {
                "category": "general",
                "title": "Deal is close on this model",
                "detail": (
                    "Fine-tune with real cap sheets (exceptions, apron tiers, BYC, ST restrictions). "
                    "Use the pick catalog and player search to stress-test small changes."
                ),
            }
        )

    return out


def build_verdict(
    label_a: str,
    label_b: str,
    tv_a: float,
    tv_b: float,
    trade_legal: bool,
    sal_a_out: float,
    sal_b_out: float,
    band_a_label: str,
    band_b_label: str,
) -> dict[str, Any]:
    surplus = tv_a - tv_b  # positive => A gives more value than receives
    margin = abs(surplus)
    if surplus > 5:
        verdict_team = label_b
        reason = (
            f"{label_a}'s package (TV {tv_a:.1f}) exceeds {label_b} ({tv_b:.1f}) by {margin:.1f} points — "
            f"{label_b} adds more talent/value on paper."
        )
    elif surplus < -5:
        verdict_team = label_a
        reason = (
            f"{label_b}'s package (TV {tv_b:.1f}) exceeds {label_a} ({tv_a:.1f}) by {margin:.1f} points — "
            f"{label_a} adds more talent/value on paper."
        )
    else:
        verdict_team = "Roughly even"
        reason = "Trade values are close — fair territory for both sides."

    cap_note = (
        f"Both sides pass their chosen aggregation presets ({band_a_label} / {band_b_label}). "
        f"Still not a full CBA, BYC, or multi-team validation."
        if trade_legal
        else (
            f"Fails at least one side's aggregation preset ({band_a_label} / {band_b_label}). "
            f"Adjust salaries (or match-salary overrides for BYC), apron tier, or use professional cap software."
        )
    )
    return {
        "surplus_direction": "team_a" if surplus > 0 else ("team_b" if surplus < 0 else "even"),
        "surplus_magnitude": round(margin, 2),
        "verdict_team": verdict_team,
        "reason": reason,
        "salary_cap_note": cap_note,
        "salary_summary": {
            f"{label_a}_outgoing_mm": round(sal_a_out, 2),
            f"{label_b}_outgoing_mm": round(sal_b_out, 2),
        },
    }


def analyze_trade(
    pool: pd.DataFrame,
    team_a: dict[str, Any],
    team_b: dict[str, Any],
    league_year: int | None = None,
) -> dict[str, Any]:
    """
    team_* keys: label, salary_bracket (below_first_apron|first_apron|second_apron),
    players (query, team?, player_id?, match_salary_mm? for BYC/poison-pill),
    picks (pick ids).
    """
    label_a = team_a.get("label") or "Team A"
    label_b = team_b.get("label") or "Team B"
    bracket_a = team_a.get("salary_bracket") or "below_first_apron"
    bracket_b = team_b.get("salary_bracket") or "below_first_apron"
    ly = int(
        league_year
        or team_a.get("league_year")
        or team_b.get("league_year")
        or 2025
    )

    rows_a: list[dict[str, Any]] = []
    rows_b: list[dict[str, Any]] = []
    radar_players_a: list[tuple[str, list[float], str]] = []
    radar_players_b: list[tuple[str, list[float], str]] = []

    colors = list(CHART_PALETTE)

    idx = 0
    for spec in team_a.get("players") or []:
        query = spec.get("query") or spec.get("name") or ""
        team_hint = spec.get("team")
        row = find_player_row(pool, query, team_hint, spec.get("player_id"))
        d = row.to_dict()
        base_mm = float(d.get("salary_mm") or 0.0)
        mo = spec.get("match_salary_mm")
        d["aggregation_salary_mm"] = float(mo) if mo is not None else base_mm
        d["salary_mm"] = base_mm
        d["asset_type"] = "player"
        d["side"] = label_a
        d["chart_color"] = colors[idx % len(colors)]
        d["short_label"] = str(d.get("player_name", query))[:24]
        rows_a.append(d)
        radar_players_a.append(
            (d["short_label"], radar_dimensions(row, pool), d["chart_color"])
        )
        idx += 1

    for spec in team_b.get("players") or []:
        query = spec.get("query") or spec.get("name") or ""
        team_hint = spec.get("team")
        row = find_player_row(pool, query, team_hint, spec.get("player_id"))
        d = row.to_dict()
        base_mm = float(d.get("salary_mm") or 0.0)
        mo = spec.get("match_salary_mm")
        d["aggregation_salary_mm"] = float(mo) if mo is not None else base_mm
        d["salary_mm"] = base_mm
        d["asset_type"] = "player"
        d["side"] = label_b
        d["chart_color"] = colors[idx % len(colors)]
        d["short_label"] = str(d.get("player_name", query))[:24]
        rows_b.append(d)
        radar_players_b.append(
            (d["short_label"], radar_dimensions(row, pool), d["chart_color"])
        )
        idx += 1

    pick_rows_a: list[dict[str, Any]] = []
    for pid in team_a.get("picks") or []:
        pr = resolve_pick(pid, league_year=ly)
        pick_rows_a.append(
            {
                "asset_type": "pick",
                "player_name": pr["label"],
                "team": label_a,
                "age": None,
                "salary_mm": 0.0,
                "contract_years_remaining": None,
                "trade_value_score": pr["trade_value"],
                "pts": None,
                "ast": None,
                "reb": None,
                "bpm": None,
                "vorp": None,
                "health_score": None,
                "contract_efficiency": None,
                "talent_score": None,
                "contract_value_score": None,
                "side": label_a,
                "pick_id": pr["id"],
                "chart_color": colors[idx % len(colors)],
                "short_label": pr["label"][:28],
                "ml_value_score": None,
                "ml_vorp_predicted": None,
                "trade_value_hybrid": float(pr["trade_value"]),
            }
        )
        idx += 1

    pick_rows_b: list[dict[str, Any]] = []
    for pid in team_b.get("picks") or []:
        pr = resolve_pick(pid, league_year=ly)
        pick_rows_b.append(
            {
                "asset_type": "pick",
                "player_name": pr["label"],
                "team": label_b,
                "age": None,
                "salary_mm": 0.0,
                "contract_years_remaining": None,
                "trade_value_score": pr["trade_value"],
                "pts": None,
                "ast": None,
                "reb": None,
                "bpm": None,
                "vorp": None,
                "health_score": None,
                "contract_efficiency": None,
                "talent_score": None,
                "contract_value_score": None,
                "side": label_b,
                "pick_id": pr["id"],
                "chart_color": colors[idx % len(colors)],
                "short_label": pr["label"][:28],
                "ml_value_score": None,
                "ml_vorp_predicted": None,
                "trade_value_hybrid": float(pr["trade_value"]),
            }
        )
        idx += 1

    tv_a_players = sum(float(r["trade_value_score"]) for r in rows_a)
    tv_b_players = sum(float(r["trade_value_score"]) for r in rows_b)
    tv_a_picks = sum(float(r["trade_value_score"]) for r in pick_rows_a)
    tv_b_picks = sum(float(r["trade_value_score"]) for r in pick_rows_b)
    tv_a = tv_a_players + tv_a_picks
    tv_b = tv_b_players + tv_b_picks

    ml_scores_loaded = bool(
        "ml_value_score" in pool.columns and pool["ml_value_score"].notna().any()
    )

    if ml_scores_loaded:

        def _tv_ml_strict(r: dict[str, Any]) -> float:
            mv = r.get("ml_value_score")
            if mv is None:
                return float(r.get("trade_value_score", 0) or 0)
            try:
                f = float(mv)
                if np.isnan(f):
                    return float(r.get("trade_value_score", 0) or 0)
                return f
            except (TypeError, ValueError):
                return float(r.get("trade_value_score", 0) or 0)

        tv_a_ml_players = sum(_tv_ml_strict(r) for r in rows_a)
        tv_b_ml_players = sum(_tv_ml_strict(r) for r in rows_b)
        tv_a_ml = tv_a_ml_players + tv_a_picks
        tv_b_ml = tv_b_ml_players + tv_b_picks
    else:
        tv_a_ml_players = tv_b_ml_players = tv_a_ml = tv_b_ml = 0.0

    sal_a = sum(float(r["aggregation_salary_mm"]) for r in rows_a) + sum(
        float(r["salary_mm"]) for r in pick_rows_a
    )
    sal_b = sum(float(r["aggregation_salary_mm"]) for r in rows_b) + sum(
        float(r["salary_mm"]) for r in pick_rows_b
    )

    ok_a, max_a, band_a = side_is_legal(sal_a, sal_b, bracket_a)
    ok_b, max_b, band_b = side_is_legal(sal_b, sal_a, bracket_b)
    trade_legal = ok_a and ok_b

    all_profile = rows_a + pick_rows_a + rows_b + pick_rows_b

    # Bar chart: players only (matches your screenshots); picks in table + totals
    bar_players = rows_a + rows_b
    bar_labels = [r["short_label"] for r in bar_players]
    bar_colors = [r["chart_color"] for r in bar_players]

    def _fv(key: str, r: dict) -> float | None:
        v = r.get(key)
        if v is None:
            return None
        return float(v)

    bar_metrics: dict[str, list[float | None]] = {
        "Trade value": [_fv("trade_value_score", r) for r in bar_players],
        "Talent": [_fv("talent_score", r) for r in bar_players],
        "Contract": [_fv("contract_value_score", r) for r in bar_players],
        "Salary ($M)": [_fv("salary_mm", r) for r in bar_players],
        "Age": [_fv("age", r) for r in bar_players],
        "PTS": [_fv("pts", r) for r in bar_players],
        "AST": [_fv("ast", r) for r in bar_players],
        "REB": [_fv("reb", r) for r in bar_players],
        "BPM": [_fv("bpm", r) for r in bar_players],
    }
    if ml_scores_loaded:
        bar_metrics["ML value (0–100)"] = [_fv("ml_value_score", r) for r in bar_players]
        bar_metrics["Hybrid TV"] = [_fv("trade_value_hybrid", r) for r in bar_players]

    # Package radar: average dimensions per side (players only)
    def _avg_radar(entries: list[tuple[str, list[float], str]]) -> list[float] | None:
        if not entries:
            return None
        ar = np.mean([e[1] for e in entries], axis=0)
        return [float(x) for x in ar]

    pkg_a = _avg_radar(radar_players_a)
    pkg_b = _avg_radar(radar_players_b)

    radar_series = []
    for label, vals, col in radar_players_a:
        radar_series.append({"label": f"{label}", "data": vals, "color": col, "side": label_a})
    for label, vals, col in radar_players_b:
        radar_series.append({"label": f"{label}", "data": vals, "color": col, "side": label_b})

    if pkg_a is not None:
        radar_series.append(
            {
                "label": f"Package {label_a}",
                "data": pkg_a,
                "color": PACKAGE_COLOR_A,
                "side": label_a,
                "dashed": True,
            }
        )
    if pkg_b is not None:
        radar_series.append(
            {
                "label": f"Package {label_b}",
                "data": pkg_b,
                "color": PACKAGE_COLOR_B,
                "side": label_b,
                "dashed": True,
            }
        )

    verdict = build_verdict(
        label_a,
        label_b,
        tv_a,
        tv_b,
        trade_legal,
        sal_a,
        sal_b,
        band_a.short_label,
        band_b.short_label,
    )
    verdict_ml = (
        build_verdict(
            label_a,
            label_b,
            tv_a_ml,
            tv_b_ml,
            trade_legal,
            sal_a,
            sal_b,
            band_a.short_label,
            band_b.short_label,
        )
        if ml_scores_loaded
        else None
    )
    balance_suggestions = build_balance_suggestions(
        label_a,
        label_b,
        sal_a,
        sal_b,
        ok_a,
        ok_b,
        max_a,
        max_b,
        tv_a,
        tv_b,
        bracket_a,
        bracket_b,
    )

    return {
        "team_a_label": label_a,
        "team_b_label": label_b,
        "profiles": [
            {
                "player_name": p.get("player_name"),
                "team": p.get("team"),
                "asset_type": p.get("asset_type", "player"),
                "age": p.get("age"),
                "salary_mm": p.get("salary_mm"),
                "aggregation_salary_mm": round(float(p.get("aggregation_salary_mm", p.get("salary_mm", 0)) or 0), 3)
                if p.get("asset_type") == "player"
                else None,
                "contract_years_remaining": p.get("contract_years_remaining"),
                "trade_value_score": round(float(p.get("trade_value_score", 0)), 2),
                "ml_value_score": round(float(p["ml_value_score"]), 2)
                if p.get("ml_value_score") is not None and not pd.isna(p.get("ml_value_score"))
                else None,
                "ml_vorp_predicted": round(float(p["ml_vorp_predicted"]), 3)
                if p.get("ml_vorp_predicted") is not None and not pd.isna(p.get("ml_vorp_predicted"))
                else None,
                "trade_value_hybrid": round(float(p.get("trade_value_hybrid", p.get("trade_value_score", 0))), 2)
                if p.get("trade_value_hybrid") is not None and not pd.isna(p.get("trade_value_hybrid"))
                else round(float(p.get("trade_value_score", 0)), 2),
                "talent_score": round(float(p["talent_score"]), 2) if p.get("talent_score") is not None else None,
                "contract_value_score": round(float(p["contract_value_score"]), 2)
                if p.get("contract_value_score") is not None
                else None,
                "pts": p.get("pts"),
                "ast": p.get("ast"),
                "reb": p.get("reb"),
                "bpm": p.get("bpm"),
                "vorp": p.get("vorp"),
                "health_score": p.get("health_score"),
                "contract_efficiency": p.get("contract_efficiency"),
                "side": p.get("side"),
            }
            for p in all_profile
        ],
        "salary": {
            "league_year": ly,
            "team_a_bracket": bracket_a,
            "team_b_bracket": bracket_b,
            "team_a_band": band_a.short_label,
            "team_b_band": band_b.short_label,
            "team_a_multiplier": band_a.multiplier,
            "team_b_multiplier": band_b.multiplier,
            "team_a_cushion_mm": band_a.cushion_mm,
            "team_b_cushion_mm": band_b.cushion_mm,
            "team_a_band_note": band_a.explanation,
            "team_b_band_note": band_b.explanation,
            "team_a_outgoing_mm": round(sal_a, 2),
            "team_b_outgoing_mm": round(sal_b, 2),
            "team_a_incoming_mm": round(sal_b, 2),
            "team_b_incoming_mm": round(sal_a, 2),
            "team_a_max_outgoing_mm": round(max_a, 2),
            "team_b_max_outgoing_mm": round(max_b, 2),
            "team_a_ok": ok_a,
            "team_b_ok": ok_b,
            "trade_legal": trade_legal,
            "disclaimer": (
                "Aggregation presets are educational. Real legality requires team cap sheets, "
                "exceptions, BYC, S&T rules, and multi-team stepping."
            ),
        },
        "meta": {
            "league_year": ly,
            "trade_value_blend": "62% talent / 38% contract value (on-court vs deal shape)",
            "ml_scores_loaded": ml_scores_loaded,
            "ml_model_note": (
                "ml_value_score is from an offline model predicting VORP from box/minutes/salary features; "
                "see artifacts/ml_metrics.json. Not live inference."
            ),
            "trade_value_hybrid_note": (
                "trade_value_hybrid = 50% heuristic trade_value_score + 50% ml_value_score when ML row exists."
            ),
        },
        "trade_value": {
            "team_a_total": round(tv_a, 2),
            "team_b_total": round(tv_b, 2),
            "team_a_from_players": round(tv_a_players, 2),
            "team_b_from_players": round(tv_b_players, 2),
            "team_a_from_picks": round(tv_a_picks, 2),
            "team_b_from_picks": round(tv_b_picks, 2),
            "surplus_for_team_a": round(tv_a - tv_b, 2),
            **(
                {
                    "team_a_total_ml": round(tv_a_ml, 2),
                    "team_b_total_ml": round(tv_b_ml, 2),
                    "team_a_from_players_ml": round(tv_a_ml_players, 2),
                    "team_b_from_players_ml": round(tv_b_ml_players, 2),
                    "surplus_for_team_a_ml": round(tv_a_ml - tv_b_ml, 2),
                }
                if ml_scores_loaded
                else {}
            ),
        },
        "charts": {
            "bar": {
                "labels": bar_labels,
                "colors": bar_colors,
                "metrics": bar_metrics,
            },
            "radar": {"labels": RADAR_LABELS, "series": radar_series},
        },
        "verdict": verdict,
        "verdict_ml": verdict_ml,
        "balance_suggestions": balance_suggestions,
    }
