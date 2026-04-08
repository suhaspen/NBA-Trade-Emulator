"""
Offline training: predict VORP from box/minutes/salary features (VORP not in X).

Outputs:
  - data/ml_player_scores.csv — player_id, ml_vorp_predicted, ml_value_score
  - artifacts/ml_metrics.json — split sizes, Ridge + RF val/test metrics, chosen model
  - artifacts/ml_vorp_model.joblib — fitted sklearn Pipeline (optional load for re-inference)

Run from repo root:
  python -m ml.train_predict_vorp
  python -m ml.train_predict_vorp --input data/players.csv --seed 42
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path

import joblib
import numpy as np
import pandas as pd
from sklearn.ensemble import RandomForestRegressor
from sklearn.impute import SimpleImputer
from sklearn.linear_model import Ridge
from sklearn.metrics import mean_absolute_error, mean_squared_error, r2_score
from sklearn.model_selection import train_test_split
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import StandardScaler

# Target: real VORP in CSV. Features: everything except advanced stats used as target proxies.
TARGET_COL = "vorp"
FEATURE_COLS = [
    "age",
    "pts",
    "ast",
    "reb",
    "stl",
    "blk",
    "ts_pct",
    "games_played",
    "min_per_game",
    "salary_mm",
    "contract_years_remaining",
]

RANDOM_STATE = 42


def _prepare_frame(df: pd.DataFrame) -> pd.DataFrame:
    out = df.copy()
    sal = pd.to_numeric(out.get("salary_2023_24"), errors="coerce").fillna(0.0) / 1_000_000.0
    out["salary_mm"] = sal
    if "contract_years_remaining" not in out.columns:
        out["contract_years_remaining"] = 0.0
    out["contract_years_remaining"] = pd.to_numeric(out["contract_years_remaining"], errors="coerce").fillna(0.0)
    for c in FEATURE_COLS:
        if c not in out.columns:
            out[c] = 0.0
        else:
            out[c] = pd.to_numeric(out[c], errors="coerce")
    out[TARGET_COL] = pd.to_numeric(out[TARGET_COL], errors="coerce")
    out = out.dropna(subset=[TARGET_COL])
    return out


def _make_ridge() -> Pipeline:
    return Pipeline(
        steps=[
            ("imputer", SimpleImputer(strategy="median")),
            ("scaler", StandardScaler()),
            ("model", Ridge(alpha=2.0)),
        ]
    )


def _make_rf() -> Pipeline:
    return Pipeline(
        steps=[
            ("imputer", SimpleImputer(strategy="median")),
            (
                "model",
                RandomForestRegressor(
                    n_estimators=200,
                    max_depth=8,
                    min_samples_leaf=3,
                    random_state=RANDOM_STATE,
                    n_jobs=-1,
                ),
            ),
        ]
    )


def _metrics_dict(y_true: np.ndarray, y_pred: np.ndarray) -> dict:
    return {
        "mae": float(mean_absolute_error(y_true, y_pred)),
        "rmse": float(mean_squared_error(y_true, y_pred) ** 0.5),
        "r2": float(r2_score(y_true, y_pred)),
    }


def train_and_export(
    input_csv: Path,
    out_scores_csv: Path,
    out_metrics_json: Path,
    out_model_joblib: Path,
    seed: int = RANDOM_STATE,
) -> dict:
    raw = pd.read_csv(input_csv)
    if "player_id" not in raw.columns:
        raise ValueError("CSV must include player_id")
    df = _prepare_frame(raw)
    if len(df) < 30:
        raise ValueError(f"Need at least 30 rows with {TARGET_COL}; got {len(df)}")

    X = df[FEATURE_COLS]
    y = df[TARGET_COL].values
    ids = df["player_id"].astype(int)

    X_train, X_temp, y_train, y_temp = train_test_split(
        X, y, test_size=0.4, random_state=seed
    )
    X_val, X_test, y_val, y_test = train_test_split(
        X_temp, y_temp, test_size=0.5, random_state=seed
    )

    ridge = _make_ridge()
    rf = _make_rf()
    ridge.fit(X_train, y_train)
    rf.fit(X_train, y_train)

    ridge_val = _metrics_dict(y_val, ridge.predict(X_val))
    rf_val = _metrics_dict(y_val, rf.predict(X_val))
    ridge_test = _metrics_dict(y_test, ridge.predict(X_test))
    rf_test = _metrics_dict(y_test, rf.predict(X_test))

    use_rf = rf_val["mae"] <= ridge_val["mae"]
    best_name = "random_forest" if use_rf else "ridge"
    best = rf if use_rf else ridge

    # Refit on train+val for deployment predictions; test metrics already locked above.
    X_tv = pd.concat([X_train, X_val], axis=0)
    y_tv = np.concatenate([y_train, y_val])
    best.fit(X_tv, y_tv)

    pred_all = best.predict(df[FEATURE_COLS])
    lo, hi = float(np.min(pred_all)), float(np.max(pred_all))
    span = hi - lo if hi - lo > 1e-9 else 1.0
    ml_value = 100.0 * (pred_all - lo) / span

    out_scores_csv.parent.mkdir(parents=True, exist_ok=True)
    scores_df = pd.DataFrame(
        {
            "player_id": ids.values,
            "ml_vorp_predicted": pred_all,
            "ml_value_score": ml_value,
        }
    )
    scores_df.to_csv(out_scores_csv, index=False)

    out_model_joblib.parent.mkdir(parents=True, exist_ok=True)
    joblib.dump(
        {
            "pipeline": best,
            "feature_cols": FEATURE_COLS,
            "target": TARGET_COL,
            "model_name": best_name,
        },
        out_model_joblib,
    )

    payload = {
        "target": TARGET_COL,
        "feature_columns": FEATURE_COLS,
        "n_rows_used": len(df),
        "n_train": len(X_train),
        "n_val": len(X_val),
        "n_test": len(X_test),
        "chosen_model": best_name,
        "ridge_validation": ridge_val,
        "ridge_test": ridge_test,
        "random_forest_validation": rf_val,
        "random_forest_test": rf_test,
        "note": (
            "Test metrics are from models fit on train only. Chosen model was refit on train+val "
            "before generating ml_player_scores.csv; scores are offline, not live inference."
        ),
    }
    out_metrics_json.parent.mkdir(parents=True, exist_ok=True)
    out_metrics_json.write_text(json.dumps(payload, indent=2), encoding="utf-8")
    return payload


def main() -> None:
    ap = argparse.ArgumentParser(description="Train VORP regression and export ML player scores CSV")
    root = Path(__file__).resolve().parents[1]
    ap.add_argument("--input", type=Path, default=root / "data" / "players.csv")
    ap.add_argument("--out-scores", type=Path, default=root / "data" / "ml_player_scores.csv")
    ap.add_argument("--out-metrics", type=Path, default=root / "artifacts" / "ml_metrics.json")
    ap.add_argument("--out-model", type=Path, default=root / "artifacts" / "ml_vorp_model.joblib")
    ap.add_argument("--seed", type=int, default=RANDOM_STATE)
    args = ap.parse_args()
    m = train_and_export(args.input, args.out_scores, args.out_metrics, args.out_model, seed=args.seed)
    print(json.dumps({k: m[k] for k in ("chosen_model", "n_rows_used", "ridge_test", "random_forest_test")}, indent=2))
    print(f"Wrote scores: {args.out_scores}")
    print(f"Wrote metrics: {args.out_metrics}")


if __name__ == "__main__":
    main()
