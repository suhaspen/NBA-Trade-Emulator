"""
Run API: uvicorn webapp:app --reload --host 0.0.0.0 --port 8000

React UI (dev): cd frontend && npm install && npm run dev  →  http://localhost:5173 (proxies /api to :8000)

Production UI: cd frontend && npm run build  →  serves frontend/dist/ from this app when present.

Set TRADE_EMULATOR_DATA=/path/to/players.csv to use your own merged export.
Player CSV updates are picked up when the file mtime changes (no server restart needed).
"""

from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Annotated, Any

import pandas as pd
from fastapi import Depends, FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, HTMLResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field

from cba_rules import BRACKETS
from picks import list_pick_options
from season_utils import nba_season_end_calendar_year, nba_season_id
from trade_logic import analyze_trade, load_player_pool

BASE_DIR = Path(__file__).resolve().parent
FRONTEND_DIST = BASE_DIR / "frontend" / "dist"
ML_METRICS_PATH = BASE_DIR / "artifacts" / "ml_metrics.json"

_pool_cache: dict[str, tuple[float, Any]] = {}


def _pool_path() -> Path:
    env_path = os.environ.get("TRADE_EMULATOR_DATA")
    return Path(env_path).resolve() if env_path else (BASE_DIR / "data" / "players.csv").resolve()


def get_pool():
    path = _pool_path()
    try:
        mtime = path.stat().st_mtime
    except OSError as e:
        raise FileNotFoundError(f"Player data not found at {path}") from e
    key = str(path)
    hit = _pool_cache.get(key)
    if hit and hit[0] == mtime:
        return hit[1]
    df = load_player_pool(path)
    _pool_cache[key] = (mtime, df)
    return df


def invalidate_pool_cache() -> None:
    _pool_cache.clear()


def get_player_pool() -> pd.DataFrame:
    """
    Cached player pool for request handlers.

    Tests should replace this via ``app.dependency_overrides[get_player_pool]``.
    """
    try:
        return get_pool()
    except FileNotFoundError as e:
        raise HTTPException(500, str(e)) from e


class PlayerSpec(BaseModel):
    query: str = Field(default="", description="Name substring, e.g. 'Gilgeous'")
    team: str | None = Field(None, description="3-letter team, e.g. OKC")
    player_id: int | None = Field(
        None, description="Stable id from NBA export column player_id, if present"
    )
    match_salary_mm: float | None = Field(
        None,
        description="Salary used for aggregation if BYC/poison pill differs from cap hit",
    )


class SideInput(BaseModel):
    label: str = "Team A"
    salary_bracket: str = Field(
        "below_first_apron",
        description="below_first_apron | first_apron | second_apron",
    )
    players: list[PlayerSpec] = Field(default_factory=list)
    picks: list[str] = Field(default_factory=list)
    league_year: int | None = Field(None, description="Season end year for pick discounting")


class TradeRequest(BaseModel):
    team_a: SideInput
    team_b: SideInput
    league_year: int = Field(
        default_factory=nba_season_end_calendar_year,
        description="Calendar year the season ends; drives pick TV decay",
    )


app = FastAPI(title="NBA Trade Emulator")

app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://127.0.0.1:5173",
        "http://localhost:5173",
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

assets_dir = FRONTEND_DIST / "assets"
if assets_dir.is_dir():
    app.mount("/assets", StaticFiles(directory=str(assets_dir)), name="react_assets")

static_dir = BASE_DIR / "static"
if static_dir.is_dir():
    app.mount("/static", StaticFiles(directory=str(static_dir)), name="static")


@app.get("/")
def index():
    react_index = FRONTEND_DIST / "index.html"
    if react_index.is_file():
        return FileResponse(react_index)
    html_path = BASE_DIR / "templates" / "index.html"
    if not html_path.exists():
        raise HTTPException(500, "No UI: build frontend (npm run build) or add templates/index.html")
    return HTMLResponse(html_path.read_text(encoding="utf-8"))


@app.get("/api/health")
def health():
    return {"ok": True}


@app.get("/api/season-config")
def season_config():
    """Current season id for NBA Stats and matching league year for the UI."""
    return {
        "nba_season_id": nba_season_id(),
        "league_year_end": nba_season_end_calendar_year(),
    }


@app.post("/api/reload-pool")
def reload_pool():
    """Clear in-memory cache so the next request re-reads the CSV from disk."""
    invalidate_pool_cache()
    return {"ok": True, "path": str(_pool_path())}


@app.get("/api/cba-brackets")
def api_cba_brackets():
    return {
        "brackets": [
            {
                "id": k,
                "short_label": v.short_label,
                "multiplier": v.multiplier,
                "cushion_mm": v.cushion_mm,
                "explanation": v.explanation,
            }
            for k, v in BRACKETS.items()
        ]
    }


@app.get("/api/ml-metrics")
def api_ml_metrics():
    """Offline training summary (written by ``python -m ml.train_predict_vorp``)."""
    if not ML_METRICS_PATH.is_file():
        return {
            "available": False,
            "detail": "Run training to create artifacts/ml_metrics.json (see README).",
        }
    return {"available": True, "metrics": json.loads(ML_METRICS_PATH.read_text(encoding="utf-8"))}


@app.get("/api/picks")
def api_picks(league_year: int | None = None):
    y = league_year if league_year is not None else nba_season_end_calendar_year()
    return {"picks": list_pick_options(league_year=y)}


@app.get("/api/teams")
def api_teams(pool: Annotated[pd.DataFrame, Depends(get_player_pool)]):
    """Distinct 3-letter team codes from the loaded player pool (sorted)."""
    codes = sorted({str(x).strip().upper() for x in pool["team"].dropna().unique() if str(x).strip()})
    return {"teams": codes}


@app.get("/api/players")
def api_players(
    pool: Annotated[pd.DataFrame, Depends(get_player_pool)],
    q: str = "",
    team: str | None = None,
    roster: bool = False,
):
    df = pool
    if team:
        df = df[df["team"].astype(str).str.upper() == team.strip().upper()]
    if q:
        mask = df["player_name"].astype(str).str.contains(q.strip(), case=False, na=False)
        df = df.loc[mask]
    if team and roster:
        # Full franchise list for trade UI (small N per team); name order for scanning
        rows = df.sort_values("player_name", ascending=True, na_position="last").head(200)
    else:
        rows = df.sort_values("trade_value_score", ascending=False).head(120)
    out = []
    for _, r in rows.iterrows():
        entry = {
            "player_name": r["player_name"],
            "team": r["team"],
            "trade_value_score": round(float(r["trade_value_score"]), 2),
            "talent_score": round(float(r.get("talent_score", 0)), 2),
            "contract_value_score": round(float(r.get("contract_value_score", 0)), 2),
            "salary_mm": round(float(r["salary_mm"]), 2),
        }
        if "player_id" in r.index and pd.notna(r["player_id"]):
            entry["player_id"] = int(r["player_id"])
        if "ml_value_score" in r.index and pd.notna(r["ml_value_score"]):
            entry["ml_value_score"] = round(float(r["ml_value_score"]), 2)
        if "ml_vorp_predicted" in r.index and pd.notna(r["ml_vorp_predicted"]):
            entry["ml_vorp_predicted"] = round(float(r["ml_vorp_predicted"]), 3)
        if "trade_value_hybrid" in r.index and pd.notna(r["trade_value_hybrid"]):
            entry["trade_value_hybrid"] = round(float(r["trade_value_hybrid"]), 2)
        out.append(entry)
    return {"players": out}


@app.post("/api/analyze")
def api_analyze(
    body: TradeRequest,
    pool: Annotated[pd.DataFrame, Depends(get_player_pool)],
):
    ly = int(body.league_year)
    try:
        payload = {
            "team_a": {
                "label": body.team_a.label,
                "salary_bracket": body.team_a.salary_bracket,
                "players": [p.model_dump() for p in body.team_a.players],
                "picks": body.team_a.picks,
                "league_year": body.team_a.league_year,
            },
            "team_b": {
                "label": body.team_b.label,
                "salary_bracket": body.team_b.salary_bracket,
                "players": [p.model_dump() for p in body.team_b.players],
                "picks": body.team_b.picks,
                "league_year": body.team_b.league_year,
            },
        }
        return analyze_trade(pool, payload["team_a"], payload["team_b"], league_year=ly)
    except ValueError as e:
        raise HTTPException(400, str(e)) from e
