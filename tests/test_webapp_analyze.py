"""HTTP-level checks for /api/analyze (pool injected; no real CSV required)."""

import pandas as pd
import pytest
from fastapi.testclient import TestClient

from webapp import app, get_player_pool


@pytest.fixture
def client_with_pool(minimal_pool_df):
    app.dependency_overrides[get_player_pool] = lambda: minimal_pool_df
    yield TestClient(app)
    app.dependency_overrides.clear()


def test_api_analyze_200_shape(client_with_pool, minimal_trade_request_balanced: dict):
    r = client_with_pool.post("/api/analyze", json=minimal_trade_request_balanced)
    assert r.status_code == 200, r.text
    data = r.json()
    for key in (
        "team_a_label",
        "team_b_label",
        "profiles",
        "salary",
        "trade_value",
        "charts",
        "verdict",
        "balance_suggestions",
        "meta",
    ):
        assert key in data
    assert isinstance(data["profiles"], list)
    assert "trade_legal" in data["salary"]
    assert "bar" in data["charts"] and "labels" in data["charts"]["bar"]


def test_api_analyze_unknown_player_400(client_with_pool):
    body = {
        "league_year": 2026,
        "team_a": {
            "label": "AAA",
            "salary_bracket": "below_first_apron",
            "players": [{"query": "Nobody Here XYZ", "player_id": None}],
            "picks": [],
        },
        "team_b": {
            "label": "BBB",
            "salary_bracket": "below_first_apron",
            "players": [{"player_id": 202, "query": ""}],
            "picks": [],
        },
    }
    r = client_with_pool.post("/api/analyze", json=body)
    assert r.status_code == 400


def test_api_analyze_unknown_pick_400(client_with_pool, minimal_trade_request_balanced: dict):
    body = {**minimal_trade_request_balanced}
    body["team_a"] = {**body["team_a"], "picks": ["invalid_pick_id___"]}
    r = client_with_pool.post("/api/analyze", json=body)
    assert r.status_code == 400


def test_api_analyze_includes_ml_when_scores_merged(monkeypatch, tmp_path, minimal_trade_request_balanced: dict):
    """Inject pool with ML columns present → response exposes ML package totals + verdict_ml."""
    from trade_logic import enrich_player_pool  # noqa: PLC0415

    from tests.minimal_pool_data import MINIMAL_PLAYER_ROWS  # noqa: PLC0415

    scores = tmp_path / "ml.csv"
    scores.write_text(
        "player_id,ml_vorp_predicted,ml_value_score\n101,3.0,95.0\n202,2.0,55.0\n",
        encoding="utf-8",
    )
    monkeypatch.setenv("TRADE_EMULATOR_ML_SCORES", str(scores))
    pool = enrich_player_pool(pd.DataFrame(MINIMAL_PLAYER_ROWS))
    assert pool["ml_value_score"].notna().any()

    from webapp import app, get_player_pool  # noqa: PLC0415
    from fastapi.testclient import TestClient  # noqa: PLC0415

    app.dependency_overrides[get_player_pool] = lambda: pool
    try:
        r = TestClient(app).post("/api/analyze", json=minimal_trade_request_balanced)
        assert r.status_code == 200
        data = r.json()
        assert data["meta"]["ml_scores_loaded"] is True
        assert "team_a_total_ml" in data["trade_value"]
        assert data["verdict_ml"] is not None
        prof = data["profiles"]
        assert any(p.get("ml_value_score") is not None for p in prof)
    finally:
        app.dependency_overrides.clear()
