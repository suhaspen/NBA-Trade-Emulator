# NBA Trade Emulator

Full-stack **hypothetical NBA trade explorer**: pick two teams, choose **educational salary-matching presets** (loose / mid / strict multipliers), add players and draft picks, then inspect **heuristic trade value**, **offline ML value (optional)**, salary checks, charts, and balance notes.

- **Backend:** FastAPI (`webapp.py`), Pydantic request bodies, CSV player pool with mtime-based cache.
- **Frontend:** React, TypeScript, Vite, Tailwind

## Architecture (high level)

| Layer | Role |
|--------|------|
| `webapp.py` | HTTP routes under `/api/*`, static `frontend/dist`, `get_player_pool()` for tests, `GET /api/ml-metrics` for offline training summary. |
| `trade_logic.py` | Load CSV → `enrich_player_pool` (heuristic + **merge `data/ml_player_scores.csv`**) → `analyze_trade` (heuristic + ML package totals when scores exist). |
| `ml/train_predict_vorp.py` | **Offline only:** train/test split, Ridge vs Random Forest, write scores CSV + `artifacts/ml_metrics.json` + `artifacts/ml_vorp_model.joblib`. |
| `cba_rules.py` | Three **preset** aggregation bands; not a full CBA simulator. |
| `picks.py` | Static pick catalog + future-year discount. |
| `season_utils.py` | Calendar-derived NBA season id / league year. |


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

Includes **offline training** on `tests/fixtures/ml_training_tiny.csv`, **ML CSV merge** tests, and **API** checks for ML fields when scores are injected.

Image includes `ml/` (training module), `artifacts/`, and `data/` (player CSV + bundled ML scores if present).

## Refreshing player data

- **Pool:** `POST /api/reload-pool` or UI “Reload data”.
- **Stats CSV:** `fetch_nba_league_stats.py`, `merge_bref_salaries.py` (see script headers).
- **After changing `players.csv`, re-run `python -m ml.train_predict_vorp`** so ML columns stay aligned.

## Optional future improvements

- Multi-season panel + proper time-based validation.
- Team-fixed effects or mixed models; calibrated uncertainty.
- Auth + saved trades.

