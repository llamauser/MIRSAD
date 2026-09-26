# Faits pour le pitch (MIRSAD)

Chaque chiffre ci-dessous provient d'un fichier produit par le code (source indiquée). Rien n'est estimé à la main.
Moyennes ± écart-type sur **10 graines**. Toutes les données sont **synthétiques** et le scénario de fraude est **simulé**.

## 0. Vocabulaire : un seul « MIRSAD »
| Nom dans le pitch | Code (`policy`, `eps`) | Ce que c'est |
|---|---|---|
| **MIRSAD** (réglage par défaut) | `mirsad`, ε = 0 | Classement par **montant en jeu** = P(fraude) × revenu attendu. C'est la configuration de la démo et des indicateurs d'accueil. |
| MIRSAD + exploration | `mirsad`, ε = 0,1 / 0,2 | Même classement, avec ε × budget réservé à l'exploration (nouveaux importateurs, nouvelles combinaisons, cas incertains). |
| Variante « probabilité seule » | `model_p` | Ablation : classement par P(fraude), sans montant. |
| Règles | `rules` | Référence : profil de risque lissé de l'importateur, puis taux de taxation le plus bas. |
| Aléatoire | `random` | Référence : sélection au hasard, même budget. |

Une version antérieure appelait « MIRSAD » à la fois `model_er` (ε = 0) et la politique `mirsad` (ε > 0). C'est corrigé : il
n'y a plus qu'une politique `mirsad` paramétrée par ε, et la grille a été relancée sous ces noms (`docs/decisions.md`).

## 1. Jeu de données (`scripts/00_download.py`)
- BACUDA / Seondong « Customs-Fraud-Detection » (licence MIT) : 100 000 déclarations, 2013, 7,58 % de fraudes,
  8 653 importateurs, 1 468 déclarants, 112 pays et 23 bureaux (anonymisés), 1 894 codes SH10.
- Montants non réalistes et devise inconnue : affichés « TND simulés ».

## 2. Scénario injecté (`results/drift_log.json`)
- Dès la semaine 26, 25 nouveaux importateurs prennent 5 % des déclarations du chapitre 87 et sous-évaluent CIF et taxes
  de 60 % : 1 918 déclarations, 7,87 M de revenu simulé (contre 8,27 M pour toutes les fraudes historiques de l'année).
- Un seul ajustement du scénario, fait avant tout résultat : part 15 % → 5 % (voir `docs/decisions.md`).

## 3. Protocole (`src/mirsad/simulate.py`)
- Étiquettes sélectives : semaines 1–2, 10 % de contrôles aléatoires. Ensuite, chaque semaine, entraînement sur les seules
  déclarations inspectées du passé, sélection de k = r × N, puis révélation des seuls cas sélectionnés.
- 240 exécutions (4 budgets × 6 politiques × 10 graines), réentraînement hebdomadaire, 435 s sur 16 cœurs
  (`results/metrics.json`).
- Tests automatiques : pas de fuite d'étiquettes, le futur ne change pas le passé, budget respecté (`tests/`).

## 4. Résultats (`results/results_table.md`, `results/key_figures.json`)
**Formulations autorisées** (toujours avec « sur données synthétiques, à budget égal ») :
1. « En contrôlant 5 % des déclarations, MIRSAD capture **39,9 % ± 11,1** du revenu récupérable, contre **5,4 % ± 0,8** pour
   une sélection aléatoire, soit environ 7 fois plus. » Précision@5 % : 43,8 % contre 9,6 %.
2. « Sur les fraudes historiques, MIRSAD capture **14,3 %** du revenu à 5 % de budget, contre **10,6 %** pour les règles
   (+34 %), et **32,7 %** contre **23,4 %** à 10 %. »
3. « À budget très serré (2 %), MIRSAD capture 28,3 % du revenu, contre 16,4 % pour les règles et 2,1 % au hasard. »
4. « Classer par montant en jeu plutôt que par probabilité seule compte : 39,9 % contre 30,7 % du revenu à 5 %. »

**À dire aussi (honnêteté)** :
- Sur le total à 5 %, MIRSAD et les règles font jeu égal (39,9 % contre 39,0 %). À 10 %, les règles font mieux sur le total
  (59,1 % contre 50,1 %) parce qu'elles verrouillent le schéma injecté de façon déterministe (95,5 % capturés).
- MIRSAD est **bimodal sur le schéma injecté** : à 5 %, il en capture 66,0 % en moyenne, mais une graine sur dix le manque
  presque entièrement (0,3 %). Les 9 autres sont entre 62 et 86 % (`results/summary_by_seed.csv`).
- Faux-vert (revenu récupérable resté en voie verte) à 5 % : 51,2 %. Un budget de 5 % ne peut pas tout voir.

## 5. L'exploration aide-t-elle ? (`results/exploration_stats.json`, test de Welch sur 10 graines)
- **Aucune différence de moyenne significative à p < 0,05**, sur aucun budget ni aucune mesure.
- Ce qu'on peut dire : à 5–10 % de budget, ε = 0,2 **améliore le pire cas** sur le schéma injecté. La graine la plus
  défavorable passe de 0,3 % à 19,8 % du revenu du schéma à 5 %, et de 14,5 % à 65,8 % à 10 %. À 10 %, le gain moyen est
  de +14,4 points (p = 0,068, non significatif).
- Coût : l'exploration réduit un peu la capture des fraudes historiques (à 10 % : 32,7 % → 28,7 %).
- Formulation autorisée : « l'exploration est un **réglage de prudence** qui réduit le risque de passer à côté d'un nouveau
  schéma, pas un gain moyen démontré ». Configuration de démo : ε = 0.

## 6. Agent d'enquête (dossiers)
- Chaîne : **LLM local sur site** (Qwen3 8B via Ollama, GPU portable RTX 4060 8 Go) → **API OpenAI** (gpt-4.1) en secours
  → **gabarit déterministe**. Chaque dossier LLM doit passer le validateur (preuves, nombres, citations verbatim, voie
  inchangée, cohérence hypothèse/preuve), avec une correction autorisée.
- Répartition des modes et durées sur les dossiers de la démo : voir `results/dossiers/index.json` (section 6 bis,
  complétée après génération).
- Exemple observé : le LLM local a inventé deux références juridiques (« REG-2024-001 ») ; le validateur les a rejetées et
  la chaîne est passée à l'API, dont le dossier a été validé.

## 7. Espèce tarifaire T18 (`results/espece_metrics_*.json`)
Jeu de 50 descriptions **construit par l'équipe** (évaluation optimiste) ; taux de droits **illustratifs**.
| Mode | Top-1 SH6 | Top-3 SH6 | Top-1 SH4 | Alertes : précision / rappel | Injections détectées |
|---|---|---|---|---|---|
| BM25 seul (sans LLM) | 56 % | 90 % | 90 % | 67 % / 55 % | 3/3 |
| BM25 + reclassement API (gpt-4.1-mini) | 98 % | 100 % | 100 % | 100 % / 64 % | 3/3 |
| BM25 + reclassement LLM local | voir `results/espece_metrics.json` après exécution | | | | |

## 8. Base légale
- Corpus chargé (`data/legal/`, extraits verbatim) : Accord de l'OMC sur l'évaluation en douane (art. 1–24), Convention de
  Kyoto révisée (OMD), Annexe générale, chapitre 6 « Contrôle douanier », et Code des douanes tunisien, art. 43–64
  (base DCAF). Les citations des dossiers sont vérifiées mot pour mot par le validateur.
- Phrase d'ancrage pour le pitch (Kyoto, norme 6.4, verbatim) : « La douane a recours à l’analyse des risques pour désigner
  les personnes et les marchandises à examiner, y compris les moyens de transport, et l'étendue de cette vérification. »

## 9. Miroir (`results/mirror_meta.json`)
- UN Comtrade 2024, Tunisie × 7 partenaires (Chine, Turquie, Italie, France, Allemagne, Espagne, Algérie ; Libye absente
  faute de données partenaire), niveau SH2. **Indicateur de priorisation, pas une preuve** : régimes suspensifs et
  entreprises totalement exportatrices expliquent une partie des écarts.

## 10. Contrôle de cohérence (`results/sanity_split.json`)
- Janvier–février → mars (toutes étiquettes) : AUC-ROC 0,80, AUC-PR 0,26 (taux de base 8,1 %). Ce n'est pas l'évaluation
  principale.

## Interdits
Gains en dinars réels ; affirmations sur le fonctionnement interne du système de la Douane ; critique du système
existant ; tout chiffre non produit par notre code ; tout article de loi absent du corpus.
