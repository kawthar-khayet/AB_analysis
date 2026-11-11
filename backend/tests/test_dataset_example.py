"""Le jeu de données d'exemple traverse tout le workflow API : aperçu, import, analyse, export."""

import csv
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from app.main import app

client = TestClient(app)
DATASET = Path(__file__).resolve().parents[2] / "data" / "relances_paiement" / "relances_paiement.csv"


@pytest.fixture(scope="module")
def csv_text() -> str:
    return DATASET.read_text(encoding="utf-8")


@pytest.fixture(scope="module")
def rows(csv_text: str) -> list[dict[str, str]]:
    return list(csv.DictReader(csv_text.splitlines()))


def _import(rows: list[dict[str, str]], metric: str, **declaration) -> dict:
    res = client.post(
        "/api/v1/datasets/import",
        json={
            "group_values": [r["variant"] for r in rows],
            "metric_values": [r[metric] for r in rows],
            "group_a_value": "control",
            "group_b_value": "treatment",
            "metric_column_name": metric,
            **declaration,
        },
    )
    assert res.status_code == 200, res.text
    return res.json()


def _analyse(dataset: dict, method: str, **params) -> dict:
    res = client.post(
        "/api/v1/analyses",
        json={"method": method, "group_a": dataset["group_a"], "group_b": dataset["group_b"], **params},
    )
    assert res.status_code == 200, res.text
    return res.json()


def test_preview_detects_columns_and_delimiter(csv_text: str) -> None:
    res = client.post("/api/v1/datasets/preview", json={"csv_text": csv_text})
    assert res.status_code == 200
    body = res.json()
    assert body["delimiter"] == ","
    assert body["row_count"] == 2400
    assert body["columns"] == [
        "invoice_id", "variant", "sector", "country", "amount_eur", "recovered", "days_to_payment",
    ]


def test_binary_metric_keeps_every_invoice(rows) -> None:
    dataset = _import(rows, "recovered", metric_type="binary",
                      binary_success_value="yes", binary_failure_value="no")
    assert dataset["report"]["n_excluded"] == 0
    assert len(dataset["group_a"]) == len(dataset["group_b"]) == 1200


@pytest.mark.parametrize("method", ["two_proportion_z", "fisher_exact"])
def test_recovery_rate_is_inconclusive(rows, method: str) -> None:
    dataset = _import(rows, "recovered", metric_type="binary",
                      binary_success_value="yes", binary_failure_value="no")
    result = _analyse(dataset, method, delta=0.02)["result"]

    assert result["estimate"]["value"] == pytest.approx(785 / 1200 - 755 / 1200)
    assert result["confidence_interval"]["lower"] < 0 < result["confidence_interval"]["upper"]
    assert result["decision"] == "fail_to_reject_null"


def test_missing_delays_are_excluded_and_traced(rows) -> None:
    dataset = _import(rows, "days_to_payment", metric_type="continuous", unit="jours")
    report = dataset["report"]

    n_missing = sum(1 for r in rows if r["days_to_payment"] == "")
    assert report["n_excluded"] == n_missing == 860
    assert [e["reason"] for e in report["exclusions"]] == ["MISSING_METRIC"]
    assert any(w["code"] == "HIGH_EXCLUSION_RATE" for w in report["warnings"])


@pytest.mark.parametrize("method", ["welch_t", "bootstrap"])
def test_treatment_pays_faster(rows, method: str) -> None:
    dataset = _import(rows, "days_to_payment", metric_type="continuous", unit="jours")
    result = _analyse(dataset, method, delta=2.0, unit="jours", seed=2026, n_resamples=2000)["result"]

    assert result["estimate"]["value"] < 0
    assert result["confidence_interval"]["upper"] < 0
    assert result["decision"] == "reject_null"


def test_result_can_be_exported_as_csv(rows) -> None:
    dataset = _import(rows, "days_to_payment", metric_type="continuous", unit="jours")
    analysis = _analyse(dataset, "welch_t", delta=2.0, unit="jours")
    res = client.post("/api/v1/exports/csv", json=analysis)
    header, row = list(csv.reader(res.content.decode("utf-8-sig").splitlines()))
    record = dict(zip(header, row))
    assert record["method"] == "welch_t"
    assert record["unit"] == "jours"
    assert int(record["n_a"]) + int(record["n_b"]) == 2400 - 860


def test_faster_payment_is_read_as_an_improvement_with_lower_is_better(rows) -> None:
    dataset = _import(rows, "days_to_payment", metric_type="continuous", unit="jours")

    naive = _analyse(dataset, "welch_t", delta=1.0, unit="jours")["interpretation"]
    assert naive["case"] == "e"  # lecture par défaut : plus haut = mieux
    assert naive["favorable_direction"] == "higher_is_better"

    outcome = _analyse(dataset, "welch_t", delta=1.0, unit="jours", favorable_direction="lower_is_better")
    interp = outcome["interpretation"]
    assert interp["case"] == "a"
    assert interp["recommendation"].startswith("Déployer la variante B")
    assert interp["favorable_direction"] == "lower_is_better"
    # L'estimé reste exprimé en B − A : seul le sens de lecture change.
    assert outcome["result"]["estimate"]["value"] < 0

    header, row = list(csv.reader(client.post("/api/v1/exports/csv", json=outcome).content.decode("utf-8-sig").splitlines()))
    assert dict(zip(header, row))["favorable_direction"] == "lower_is_better"

    pdf = client.post("/api/v1/exports/pdf", json={"analysis": outcome})
    assert pdf.status_code == 200 and pdf.content[:4] == b"%PDF"


def test_unknown_favorable_direction_is_rejected(rows) -> None:
    dataset = _import(rows, "days_to_payment", metric_type="continuous", unit="jours")
    res = client.post(
        "/api/v1/analyses",
        json={"method": "welch_t", "group_a": dataset["group_a"], "group_b": dataset["group_b"],
              "favorable_direction": "smaller_is_better"},
    )
    assert res.status_code == 422
