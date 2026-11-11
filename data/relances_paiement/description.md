# Jeu de données : relances de paiement (synthétique)

**Fichier :** `relances_paiement.csv` (2 400 lignes, séparateur `,`, UTF-8)
**Générateur :** `generate.py`, avec la graine fixe `2026`. Relancer le script redonne exactement le même fichier.

Les données sont **entièrement simulées**. Elles ne contiennent aucune donnée réelle de client ou d'entreprise.

## Scénario

Des factures impayées sont affectées **au hasard** (randomisation 50/50) à deux procédures de relance :

| Valeur de `variant` | Groupe | Procédure |
| --- | --- | --- |
| `control` | A | Relance par e-mail uniquement (procédure actuelle) |
| `treatment` | B | Relance par e-mail + appel téléphonique à J+7 |

Question métier : *l'appel téléphonique améliore-t-il le recouvrement ?*

## Colonnes

| Colonne | Type | Description |
| --- | --- | --- |
| `invoice_id` | identifiant | Identifiant unique de la facture (`INV00001`…) |
| `variant` | groupe | `control` (A) ou `treatment` (B) |
| `sector` | catégorie | Secteur du débiteur (BTP, Commerce, Industrie, Services, Transport) |
| `country` | catégorie | Pays du débiteur (FR, MA, ES, DE, IT) |
| `amount_eur` | continue | Montant de la facture en euros (log-normal) |
| `recovered` | **binaire** | `yes` si la facture est payée sous 60 jours, sinon `no` |
| `days_to_payment` | **continue** | Jours entre la relance et le paiement. **Vide** si `recovered = no` |

## Deux analyses possibles

| Métrique | Mapping à l'import | Méthodes compatibles |
| --- | --- | --- |
| `recovered` | binaire, succès = `yes`, échec = `no` | `two_proportion_z`, `fisher_exact` |
| `days_to_payment` | continue, unité `jours` | `welch_t`, `bootstrap` |

Pour `days_to_payment`, l'import écarte **860 lignes vides** (motif `MISSING_METRIC`) et lève l'alerte
`HIGH_EXCLUSION_RATE`. C'est voulu : les exclusions sont tracées, jamais silencieuses.

## Vérité terrain de la simulation

| Paramètre | control (A) | treatment (B) | Écart B − A |
| --- | --- | --- | --- |
| Taux de recouvrement simulé | 62 % | 67 % | +5 pts |
| Délai médian simulé (log-normal, σ = 0,55, tronqué à 60 j) | 28 j | 24 j | −4 j |

## Valeurs observées dans le fichier

| | control (A) | treatment (B) |
| --- | --- | --- |
| Factures | 1 200 | 1 200 |
| Recouvrées | 755 (62,9 %) | 785 (65,4 %) |
| Délai moyen (recouvrées) | 28,6 j | 25,8 j |
| Délai médian (recouvrées) | 26,6 j | 23,8 j |

Résultats attendus dans l'application (α = 5 %) :

* **Taux de recouvrement :** +2,5 pts, IC 95 % ≈ [−1,3 ; +6,3], p ≈ 0,20, donc **non concluant**. Le vrai écart
  (+5 pts) existe pourtant. Avec 1 200 factures par groupe, la puissance est trop faible pour le détecter
  de façon fiable. Ne pas rejeter H0 ne prouve pas que les deux procédures se valent.
* **Délai de paiement :** −2,8 j, IC 95 % ≈ [−4,0 ; −1,5], p < 0,001, donc **significatif** (Welch et bootstrap concordent).

## Limite à connaître

`days_to_payment` n'existe que pour les factures **recouvrées**. Comparer les délais revient donc à
conditionner sur un résultat qui peut lui-même dépendre du traitement. Si l'appel fait payer des débiteurs
habituellement lents, le groupe B recouvré n'est plus comparable au groupe A recouvré : c'est un **biais de
sélection**. La métrique principale, randomisée sans conditionnement, reste `recovered`.
