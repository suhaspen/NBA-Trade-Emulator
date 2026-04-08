"""
Draft pick trade-value presets (0–100 scale, comparable to player trade_value_score).

``draft_year`` plus ``league_year`` in resolve_pick applies a small future discount.
Salary is always $0 for picks in salary matching.
"""

import os

PICK_FUTURE_DECAY = float(os.environ.get("PICK_FUTURE_DECAY", "0.94"))

PICK_CATALOG = {
    "2025_1st_unprotected": {
        "label": "2025 1st (unprotected)",
        "trade_value": 30,
        "salary_mm": 0.0,
        "draft_year": 2025,
    },
    "2026_1st_unprotected": {
        "label": "2026 1st (unprotected)",
        "trade_value": 27,
        "salary_mm": 0.0,
        "draft_year": 2026,
    },
    "2027_1st_unprotected": {
        "label": "2027 1st (unprotected)",
        "trade_value": 24,
        "salary_mm": 0.0,
        "draft_year": 2027,
    },
    "2028_1st_unprotected": {
        "label": "2028 1st (unprotected)",
        "trade_value": 21,
        "salary_mm": 0.0,
        "draft_year": 2028,
    },
    "2025_1st_top10_prot": {
        "label": "2025 1st (top-10 protected)",
        "trade_value": 22,
        "salary_mm": 0.0,
        "draft_year": 2025,
    },
    "2026_1st_lottery_prot": {
        "label": "2026 1st (lottery protected)",
        "trade_value": 18,
        "salary_mm": 0.0,
        "draft_year": 2026,
    },
    "2025_2nd": {
        "label": "2025 2nd round",
        "trade_value": 4,
        "salary_mm": 0.0,
        "draft_year": 2025,
    },
    "2026_2nd": {
        "label": "2026 2nd round",
        "trade_value": 3.5,
        "salary_mm": 0.0,
        "draft_year": 2026,
    },
    "2027_2nd": {
        "label": "2027 2nd round",
        "trade_value": 3,
        "salary_mm": 0.0,
        "draft_year": 2027,
    },
    "swap_2026_favorable": {
        "label": "2026 pick swap (best of)",
        "trade_value": 6,
        "salary_mm": 0.0,
        "draft_year": 2026,
    },
}


def list_pick_options(league_year: int = 2025):
    """Omit picks whose draft year already passed for this season-end model year."""
    rows = []
    ly = int(league_year)
    for k, v in PICK_CATALOG.items():
        dy = v.get("draft_year")
        if dy is not None and int(dy) < ly:
            continue
        r = resolve_pick(k, league_year=ly)
        rows.append({"id": r["id"], "label": r["label"], "trade_value": r["trade_value"]})
    return rows


def resolve_pick(pick_id: str, *, league_year: int = 2025) -> dict:
    if pick_id not in PICK_CATALOG:
        raise ValueError(f"Unknown pick id: {pick_id}")
    base = PICK_CATALOG[pick_id]
    tv = float(base["trade_value"])
    dy = base.get("draft_year")
    if dy is not None:
        years_ahead = max(0, int(dy) - int(league_year))
        tv = tv * (PICK_FUTURE_DECAY**years_ahead)
    return {
        "id": pick_id,
        "label": base["label"],
        "trade_value": round(tv, 3),
        "salary_mm": float(base["salary_mm"]),
    }
