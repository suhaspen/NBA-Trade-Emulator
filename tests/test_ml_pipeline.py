"""Offline training: deterministic fixture, schema, and metrics JSON."""

import json
from pathlib import Path

import pandas as pd

from ml.train_predict_vorp import train_and_export

FIXTURE = Path(__file__).resolve().parent / "fixtures" / "ml_training_tiny.csv"


def test_train_and_export_fixture(tmp_path):
    out_scores = tmp_path / "ml_player_scores.csv"
    out_metrics = tmp_path / "ml_metrics.json"
    out_model = tmp_path / "model.joblib"
    payload = train_and_export(FIXTURE, out_scores, out_metrics, out_model, seed=42)

    assert payload["n_rows_used"] >= 30
    assert payload["chosen_model"] in ("ridge", "random_forest")
    assert "ridge_test" in payload and "random_forest_test" in payload

    scores = pd.read_csv(out_scores)
    assert list(scores.columns) == ["player_id", "ml_vorp_predicted", "ml_value_score"]
    assert len(scores) == payload["n_rows_used"]
    assert scores["ml_value_score"].between(0, 100).all()

    meta = json.loads(out_metrics.read_text(encoding="utf-8"))
    assert meta["target"] == "vorp"
    assert len(meta["feature_columns"]) >= 8
