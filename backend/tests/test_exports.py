"""Tests des routes d'export PDF, JSON et CSV."""

import csv
import io

from fastapi.testclient import TestClient
from app.main import app

client = TestClient(app)


def test_export_pdf_and_json() -> None:
    # 1. Obtenir un résultat d'analyse valide
    analysis_payload = {
        "method": "welch_t",
        "group_a": [10.0, 11.0, 10.5, 9.8, 12.0],
        "group_b": [14.0, 15.0, 13.5, 16.0, 14.8],
        "alpha": 0.05,
        "alternative": "two_sided",
        "delta": 1.0,
        "unit": "sec",
    }
    ana_res = client.post("/api/v1/analyses", json=analysis_payload)
    assert ana_res.status_code == 200
    analysis_data = ana_res.json()

    # 2. Test export PDF
    pdf_res = client.post(
        "/api/v1/exports/pdf",
        json={
            "analysis": analysis_data,
            "experiment_name": "Test Experience",
            "author": "Analyste Test",
        },
    )
    assert pdf_res.status_code == 200
    assert pdf_res.headers["content-type"] == "application/pdf"
    assert pdf_res.content[:4] == b"%PDF"

    # 3. Test export JSON
    json_res = client.post("/api/v1/exports/json", json=analysis_data)
    assert json_res.status_code == 200
    assert json_res.headers["content-type"] == "application/json"


def _analysis(method: str, a: list[float], b: list[float]) -> dict:
    res = client.post(
        "/api/v1/analyses",
        json={"method": method, "group_a": a, "group_b": b, "delta": 0.01, "seed": 7, "n_resamples": 500},
    )
    assert res.status_code == 200
    return res.json()


def _read_csv(content: bytes) -> list[list[str]]:
    assert content.startswith(b"\xef\xbb\xbf")  # BOM UTF-8 pour Excel
    return list(csv.reader(io.StringIO(content.decode("utf-8-sig"))))


def test_export_result_csv_is_one_flat_row() -> None:
    analysis = _analysis("two_proportion_z", [1] * 30 + [0] * 70, [1] * 45 + [0] * 55)
    res = client.post("/api/v1/exports/csv", json=analysis)

    assert res.status_code == 200
    assert res.headers["content-type"].startswith("text/csv")
    assert "resultat_ab_test.csv" in res.headers["content-disposition"]

    header, row, *rest = _read_csv(res.content)
    assert rest == []
    record = dict(zip(header, row))
    assert record["method"] == "two_proportion_z"
    assert record["n_a"] == "100" and record["n_b"] == "100"
    assert float(record["estimate_b_minus_a"]) == analysis["result"]["estimate"]["value"]
    assert float(record["ci_lower"]) < float(record["estimate_b_minus_a"]) < float(record["ci_upper"])
    assert float(record["p_value"]) == analysis["result"]["p_value"]
    assert record["interpretation_case"] == analysis["interpretation"]["case"]


def test_export_result_csv_for_bootstrap_keeps_resampling_metadata() -> None:
    analysis = _analysis("bootstrap", [10.0, 11.0, 12.0, 13.0, 9.0, 10.5], [12.0, 13.5, 14.0, 12.5, 15.0, 13.0])
    header, row = _read_csv(client.post("/api/v1/exports/csv", json=analysis).content)
    record = dict(zip(header, row))
    assert record["method"] == "bootstrap"
    assert record["seed"] == "7"
    assert record["n_resamples"] == "500"
    assert record["ci_method"] == "percentile_bootstrap"


def test_export_data_csv_lists_every_observation_with_its_group() -> None:
    payload = {"group_a": [1.5, 2.0], "group_b": [3.0], "label_a": "control", "label_b": "treatment",
               "metric_name": "days_to_payment"}
    res = client.post("/api/v1/exports/csv/data", json=payload)

    assert res.status_code == 200
    rows = _read_csv(res.content)
    assert rows == [["group", "days_to_payment"], ["control", "1.5"], ["control", "2.0"], ["treatment", "3.0"]]
