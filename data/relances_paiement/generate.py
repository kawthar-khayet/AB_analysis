"""Génère le jeu de données synthétique ``relances_paiement.csv`` (graine fixe).

Scénario : des factures impayées sont affectées au hasard à deux procédures de relance.
* ``control``   : relance par e-mail uniquement (procédure actuelle) ;
* ``treatment`` : relance par e-mail + appel téléphonique à J+7.

Lancer depuis la racine du dépôt :  python data/relances_paiement/generate.py
Le fichier produit est versionné ; relancer le script le régénère à l'identique.
"""

from __future__ import annotations

import csv
from pathlib import Path

import numpy as np

SEED = 2026
N_PER_GROUP = 1200
OUT = Path(__file__).with_name("relances_paiement.csv")

SECTORS = ["BTP", "Commerce", "Industrie", "Services", "Transport"]
COUNTRIES = ["FR", "MA", "ES", "DE", "IT"]

#: Vérité terrain de la simulation (documentée dans description.md).
TRUE_RECOVERY_RATE = {"control": 0.62, "treatment": 0.67}
TRUE_MEDIAN_DAYS = {"control": 28.0, "treatment": 24.0}
LOG_SD_DAYS = 0.55


def _days_within_window(rng: np.random.Generator, median: float) -> float:
    """Délai log-normal, tiré à nouveau tant qu'il dépasse la fenêtre de 60 jours."""
    while True:
        days = rng.lognormal(np.log(median), LOG_SD_DAYS)
        if days <= 60.0:
            return days


def main() -> None:
    rng = np.random.default_rng(SEED)
    variants = np.array(["control"] * N_PER_GROUP + ["treatment"] * N_PER_GROUP)
    rng.shuffle(variants)  # ordre d'arrivée aléatoire, comme dans un vrai export

    rows = []
    for i, variant in enumerate(variants, start=1):
        recovered = rng.random() < TRUE_RECOVERY_RATE[variant]
        days = _days_within_window(rng, TRUE_MEDIAN_DAYS[variant]) if recovered else None
        rows.append({
            "invoice_id": f"INV{i:05d}",
            "variant": variant,
            "sector": rng.choice(SECTORS),
            "country": rng.choice(COUNTRIES, p=[0.35, 0.25, 0.15, 0.15, 0.10]),
            "amount_eur": round(float(rng.lognormal(np.log(4500), 0.9)), 2),
            "recovered": "yes" if recovered else "no",
            # Vide si la facture n'est pas recouvrée : l'import doit tracer ces exclusions.
            "days_to_payment": "" if days is None else round(float(days), 1),
        })

    with OUT.open("w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=list(rows[0]), lineterminator="\n")
        writer.writeheader()
        writer.writerows(rows)
    print(f"{len(rows)} lignes écrites dans {OUT}")


if __name__ == "__main__":
    main()
