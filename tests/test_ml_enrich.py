"""Runtime merge of offline ML scores into enrich_player_pool."""

from pathlib import Path

import pandas as pd
import pytest

from trade_logic import enrich_player_pool, load_ml_score_lookup


def test_load_ml_score_lookup_missing_file(monkeypatch, tmp_path):
    monkeypatch.setenv("TRADE_EMULATOR_ML_SCORES", str(tmp_path / "nope.csv"))
    assert load_ml_score_lookup() is None


def test_enrich_merges_ml_scores(monkeypatch, tmp_path):
    p = tmp_path / "scores.csv"
    p.write_text(
        "player_id,ml_vorp_predicted,ml_value_score\n"
        "101,2.5,88.5\n"
        "202,1.0,42.0\n",
        encoding="utf-8",
    )
    monkeypatch.setenv("TRADE_EMULATOR_ML_SCORES", str(p))
    from tests.minimal_pool_data import MINIMAL_PLAYER_ROWS  # noqa: PLC0415

    raw = pd.DataFrame(MINIMAL_PLAYER_ROWS)
    enriched = enrich_player_pool(raw)
    row_a = enriched.loc[enriched["player_id"] == 101].iloc[0]
    assert float(row_a["ml_value_score"]) == pytest.approx(88.5)
    assert float(row_a["trade_value_hybrid"]) == pytest.approx(
        0.5 * float(row_a["trade_value_score"]) + 0.5 * 88.5
    )


def test_default_ml_scores_path_when_file_committed(monkeypatch):
    repo_data = Path(__file__).resolve().parents[1] / "data" / "ml_player_scores.csv"
    if not repo_data.is_file():
        pytest.skip("data/ml_player_scores.csv not in workspace")
    monkeypatch.delenv("TRADE_EMULATOR_ML_SCORES", raising=False)
    ml = load_ml_score_lookup()
    assert ml is not None and len(ml) > 100
