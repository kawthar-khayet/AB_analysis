"""Tests des routes de datasets, simulation et diagnostic."""

from fastapi.testclient import TestClient
from app.main import app

client = TestClient(app)


def test_csv_preview_endpoint() -> None:
    csv_data = "user_id,variant,converted\n1,control,0\n2,treatment,1\n3,control,1"
    response = client.post("/api/v1/datasets/preview", json={"csv_text": csv_data})
    assert response.status_code == 200
    data = response.json()
    assert data["columns"] == ["user_id", "variant", "converted"]
    assert data["row_count"] == 3
    assert len(data["preview_rows"]) == 3
    assert data["delimiter"] == ","


def test_dataset_import_binary() -> None:
    payload = {
        "group_values": ["A", "B", "A", "B", "A"],
        "metric_values": ["0", "1", "1", "1", "0"],
        "group_a_value": "A",
        "group_b_value": "B",
        "metric_type": "binary",
        "binary_success_value": "1",
        "binary_failure_value": "0",
    }
    response = client.post("/api/v1/datasets/import", json=payload)
    assert response.status_code == 200
    data = response.json()
    assert len(data["group_a"]) == 3
    assert len(data["group_b"]) == 2
    assert data["metric_type"] == "binary"
    assert data["report"]["n_retained"] == 5


def test_diagnostics_endpoint() -> None:
    payload = {
        "group_a": [10.0, 12.0, 11.0, 10.5, 9.8],
        "group_b": [14.0, 15.0, 13.5, 16.0, 14.8],
        "metric_type": "continuous",
        "unit": "sec",
    }
    response = client.post("/api/v1/datasets/diagnostics", json=payload)
    assert response.status_code == 200
    data = response.json()
    assert data["metric_type"] == "continuous"
    assert data["group_a"]["n"] == 5
    assert data["group_b"]["n"] == 5
    assert "balance" in data


def test_simulation_endpoints() -> None:
    res_bin = client.post("/api/v1/simulations/binary", json={"rate_a": 0.1, "rate_b": 0.15, "n_a": 50, "n_b": 50, "seed": 42})
    assert res_bin.status_code == 200
    data_bin = res_bin.json()
    assert len(data_bin["group_column"]) == 100

    res_cont = client.post("/api/v1/simulations/continuous", json={"mean_a": 10.0, "mean_b": 12.0, "sd_a": 2.0, "sd_b": 2.0, "n_a": 50, "n_b": 50, "seed": 42})
    assert res_cont.status_code == 200
    data_cont = res_cont.json()
    assert len(data_cont["metric_column"]) == 100
