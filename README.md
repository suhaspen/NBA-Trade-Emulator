# NBA Trade Emulator

Full-stack **hypothetical NBA trade explorer**: pick two teams, choose **educational salary-matching presets** (loose / mid / strict multipliers), add players and draft picks, then inspect **heuristic trade value**, **offline ML value (optional)**, salary checks, charts, and balance notes.

- **Backend:** FastAPI (`webapp.py`), Pydantic request bodies, CSV player pool with mtime-based cache.
- **Frontend:** React, TypeScript, Vite, Tailwind, Chart.js (`frontend/`).

## Architecture (high level)

| Layer | Role |
|--------|------|
| `webapp.py` | HTTP routes under `/api/*`, static `frontend/dist`, `get_player_pool()` for tests, `GET /api/ml-metrics` for offline training summary. |
| `trade_logic.py` | Load CSV → `enrich_player_pool` (heuristic + **merge `data/ml_player_scores.csv`**) → `analyze_trade` (heuristic + ML package totals when scores exist). |
| `ml/train_predict_vorp.py` | **Offline only:** train/test split, Ridge vs Random Forest, write scores CSV + `artifacts/ml_metrics.json` + `artifacts/ml_vorp_model.joblib`. |
| `cba_rules.py` | Three **preset** aggregation bands; not a full CBA simulator. |
| `picks.py` | Static pick catalog + future-year discount. |
| `season_utils.py` | Calendar-derived NBA season id / league year. |

### How trade analysis works

1. Resolve each player (`player_id` preferred; else substring + team disambiguation).
2. **Salary for matching:** `aggregation_salary_mm` defaults to cap hit; optional `match_salary_mm`.
3. **Legality:** each side: `outgoing ≤ incoming × multiplier + cushion`.
4. **Heuristic trade value:** sum of `trade_value_score` (62% talent / 38% contract-style) + pick values.
5. **ML trade value (when `data/ml_player_scores.csv` exists):** sum of per-player `ml_value_score` (0–100 scaled offline predictions) for players; picks still use the pick catalog. UI and API show **both** verdicts when ML is loaded.

### Heuristic vs offline ML

| | Heuristic `trade_value_score` | Offline ML `ml_value_score` |
|--|------------------------------|-----------------------------|
| **Where computed** | Every `enrich_player_pool` call (rules) | **Precomputed** by `python -m ml.train_predict_vorp` |
| **What it represents** | Talent + contract blend in-app | **VORP regression** from box/minutes/salary features (VORP/BPM/WS **excluded** from inputs to avoid trivial leakage) |
| **Live inference** | N/A (not a model) | **No** — scores are merged from CSV |

`trade_value_hybrid` = 50% heuristic + 50% ML when ML row exists (for comparison charts).

**Override ML file path:** `export TRADE_EMULATOR_ML_SCORES=/path/to/ml_player_scores.csv`

### ML training workflow

```bash
pip install -r requirements.txt
python -m ml.train_predict_vorp
```

Reads `data/players.csv` (or `--input`), drops rows without `vorp`, uses an **11-feature** set (age, counting stats, shooting, minutes, games, salary, contract length), **60/20/20** train/val/test split (`--seed 42`). Trains **Ridge** (baseline) and **RandomForestRegressor**, picks the lower **validation MAE**, refits on train+val, writes predictions for all usable rows.

**Outputs**

- `data/ml_player_scores.csv` — `player_id`, `ml_vorp_predicted`, `ml_value_score` (0–100 min–max on full prediction set for display).
- `artifacts/ml_metrics.json` — split sizes, val/test **MAE**, **RMSE**, **R²** for both models, chosen model name.
- `artifacts/ml_vorp_model.joblib` — fitted pipeline (reproducibility / optional reload).

**Evaluation (example on bundled data — re-run training to regenerate):** see `artifacts/ml_metrics.json` after training. Latest run on **573** players: **Ridge** chosen; test **MAE ≈ 0.51 VORP**, **R² ≈ 0.61** (single-season snapshot; not production forecasting).

### Limitations (honest)

- **Not** cap-compliant; **not** real-time NBA data in the API.
- **ML:** one-season cross-section; predicting **VORP** from proxies is **educational** — not a front-office asset model. Test metrics are **in-sample era** only; no walk-forward seasons in-repo.
- **Data leakage risk:** target and team effects are simplified; no hierarchical team model.
- Trade “fairness” remains a **linear sum of scores**, not market pricing.

## Prerequisites

- **Python** 3.11+ (3.12 recommended)
- **Node.js** 18+ and **npm**

## Local setup

### Backend (API)

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

Ensure `data/players.csv` exists (and, for ML columns in the UI, run training once or keep bundled `data/ml_player_scores.csv`).

```bash
uvicorn webapp:app --reload --host 127.0.0.1 --port 8000
```

### Frontend (dev)

```bash
cd frontend
npm install
npm run dev
```

### Single-port mode

```bash
cd frontend && npm install && npm run build && cd ..
uvicorn webapp:app --host 127.0.0.1 --port 8000
```

## Tests

```bash
pytest tests/ -q
```

Includes **offline training** on `tests/fixtures/ml_training_tiny.csv`, **ML CSV merge** tests, and **API** checks for ML fields when scores are injected.

## CI

`.github/workflows/ci.yml` — **pytest** + **`npm ci` + `npm run build`**.

## Docker

```bash
docker build -t nba-trade-emulator .
docker run --rm -p 8000:8000 nba-trade-emulator
```

Image includes `ml/` (training module), `artifacts/`, and `data/` (player CSV + bundled ML scores if present).

## Refreshing player data

- **Pool:** `POST /api/reload-pool` or UI “Reload data”.
- **Stats CSV:** `fetch_nba_league_stats.py`, `merge_bref_salaries.py` (see script headers).
- **After changing `players.csv`, re-run `python -m ml.train_predict_vorp`** so ML columns stay aligned.

## Optional future improvements

- Multi-season panel + proper time-based validation.
- Team-fixed effects or mixed models; calibrated uncertainty.
- Auth + saved trades.

## Disclaimer

Illustrative / educational only—not legal, cap, or financial advice.
