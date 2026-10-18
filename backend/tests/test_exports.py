"""Tests des routes d'export PDF et JSON."""

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
