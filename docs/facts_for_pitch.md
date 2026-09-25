# Faits pour le pitch (MIRSAD)

Chaque chiffre ci-dessous provient d'un fichier produit par le code. Rien n'est estimé à la main.

## Jeu de données (`scripts/00_download.py`)
- BACUDA / Seondong « Customs-Fraud-Detection » (licence MIT), `synthetic-imports-declarations.csv` : 100 000 déclarations, 14 colonnes, 02/01/2013 → 31/12/2013, 7,58 % frauduleuses, 8 653 importateurs, 1 468 déclarants, 112 pays et 23 bureaux (anonymisés), 1 894 codes SH10.
- Les montants sont des **montants simulés** (devise inconnue, affichés « TND simulés »).

## Scénario de fraude injecté (`results/drift_log.json`, `src/mirsad/drift.py`)
- **Simulé par l'équipe.** Dès la semaine 26, 25 nouveaux importateurs (IMPNEW…) reprennent 5 % des déclarations du chapitre 87 (choisi automatiquement : chapitre le plus volumineux avec un taux de fraude historique sous la médiane) et sous-évaluent CIF et taxes de 60 %.
- 1 918 déclarations, ~71 par semaine, 7,87 M de revenu simulé perdu, contre 8,27 M pour l'ensemble des fraudes historiques de l'année.
- Un seul ajustement du scénario : la part est passée de 15 % à 5 % **avant** tout résultat de simulation, parce qu'à 15 % le schéma pesait 3× toutes les fraudes historiques (voir `docs/decisions.md`).

## Protocole (`src/mirsad/simulate.py`, `scripts/02_simulate.py`)
- Semaines 1–2 : seules 10 % de déclarations, tirées au hasard, révèlent leur étiquette. Ensuite, de la semaine 3 à la 52 : entraînement sur les seules déclarations **inspectées** du passé, scoring de la semaine, sélection sous budget k = r·N, puis révélation des seules déclarations sélectionnées.
- Réentraînement chaque semaine ; 10 graines ; 240 exécutions (`results/metrics.json` → `grid_runtime_s`).

## Résultats (`results/results_table.md`, `results/summary_by_seed.csv`, `results/metrics.json`) : moyenne ± écart-type sur 10 graines

Source : `results/results_table.md`, tableau complet pour r ∈ {2, 5, 10, 20} %.

Formulations autorisées :
1. « À budget égal (5 % des déclarations inspectées), le classement par revenu attendu de MIRSAD capture **39,5 %** du revenu récupérable, contre **5,4 %** pour une sélection aléatoire (≈ 7×), sur données synthétiques. »
2. « Sur les fraudes historiques, MIRSAD capture 14,8 % du revenu à 5 % de budget, contre 10,6 % pour les règles (profil de risque de l'importateur), et 31,9 % contre 23,4 % à 10 %. »
3. « Sur le schéma injecté (nouveaux importateurs), les règles par profil importateur sont très robustes (67,8 % ± 1,3 à 5 %). Le modèle seul est bimodal : selon la graine, il verrouille le schéma en quelques semaines ou le manque (écart-type ≈ 27 points). »

## L'exploration aide-t-elle ? Réponse honnête
- **Non démontré.** À r = 5 %, la part du revenu du schéma injecté capturée vaut 64,7 % (ε = 0), 65,2 % (ε = 0,1) et 68,2 % (ε = 0,2), avec des écarts-types de 24 à 27 points : différences non significatives sur 10 graines.
- À r = 10 % : 74,1 % (ε = 0), 73,3 % (ε = 0,1), 79,7 % (ε = 0,2).
- L'exploration coûte un peu sur les fraudes historiques : 14,8 % → 13,9 % → 13,1 % à r = 5 %.
- Diagnostic : la politique « modèle » consacre déjà une large part de son budget aux nouveaux importateurs en général (nombreux dans ces données), et la pondération d'exploration (p(1−p) + 0,5·nouvelle combinaison + 0,5·nouvel importateur) ne distingue pas les importateurs du schéma des autres nouveaux venus.
- Enseignement : le profil de risque de l'entité (règles) et le classement par revenu attendu (modèle) sont complémentaires. Une politique hybride est une piste de travail, **non testée**.

## Contrôle de cohérence (`results/sanity_split.json`)
- Découpage simple janvier–février → mars (toutes étiquettes) : AUC-ROC 0,804, AUC-PR 0,264 (taux de base 8,1 %), Revenu@10 % = 42,5 % (classement ER). **Ce n'est pas l'évaluation principale.**
