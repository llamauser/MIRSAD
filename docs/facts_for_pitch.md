# Faits pour le pitch (MIRSAD) — organisés selon le cycle de risque

Chaque chiffre provient d'un fichier produit par le code (source indiquée). Moyennes ± écart-type sur **10 graines**,
budget 5 % sauf mention. **Données synthétiques, schémas de fraude simulés.** p = test de Welch ; « sig. » = p < 0,05.

## 0. Positionnement et vocabulaire
- Défi principal **T2** (étape ④). Défi complémentaire **T20** (étape ②). Le cahier des charges (§ 2) précise que le
  défi complémentaire « n'apporte aucun point supplémentaire » : il sert l'impact et la qualité de T2.
- T6, T5 et T12 sont des **briques qui alimentent T2**, pas des défis revendiqués. Hors périmètre, dit explicitement : T11,
  T16, T21 (données absentes), marchés publics (perspective).
- Le cycle suit le **processus de gestion des risques de l'OMD** : établir le contexte → identifier → analyser → évaluer et
  prioriser → traiter → surveiller et réexaminer (WCO Customs Risk Management Compendium). Il reprend aussi la norme 6.4 de
  Kyoto : « La douane a recours à l’analyse des risques pour désigner les personnes et les marchandises à examiner, y compris
  les moyens de transport, et l’étendue de cette vérification. » (verbatim, `data/legal/`)

| Nom | Code | Contenu |
|---|---|---|
| MIRSAD ④ seul | `mirsad`, ε = 0 | Classement par montant en jeu = P(fraude) × revenu attendu |
| MIRSAD + exploration | `mirsad`, ε = 0,1 / 0,2 | ε × budget réservé à l'exploration |
| Cycle A1 | `cycle_A1` | ④ + score entreprise ② comme variables |
| Cycle A2 | `cycle_A2` | + segments ③ : exploitation hors « Confiance », Thompson sur « Surveillé » (20 %), audits aléatoires (5 %) |
| Cycle complet (pré-enregistré) | `cycle_A3` | + alertes de tendance ⑦ (exploration portée à 30 %, orientée sur la zone signalée) |
| Variante post-hoc | `cycle_A3b` | A3, mais « Confiance » reste ciblable par montant en jeu. **Conçue après les résultats.** |

## 1. Données et scénarios
- BACUDA / Seondong (licence MIT) : 100 000 déclarations (2013), 7,58 % de fraudes, entités anonymisées, montants simulés.
- Trois schémas **simulés**, qui démarrent en semaine 26, d'environ 1 900 déclarations chacun
  (`results/cycle/scenarios.json`, `results/drift_log.json`) :
  - **sociétés écrans** : 25 nouvelles entreprises, chapitre 87, sous-évaluation de 60 % ;
  - **entreprises établies qui dérivent** : des entreprises au passé propre sous-évaluent la moitié de leurs déclarations ;
  - **réseau** : 25 nouvelles entreprises passent toutes par un même déclarant existant (chapitre 85).
- Seuils du score, des segments et du détecteur **fixés et versionnés avant l'évaluation** (git : « Cycle scaffolding »).

## 2. Résultats de référence (`results/results_table.md`, `results/exploration_stats.json`)
Schéma « sociétés écrans » ; grille de 4 budgets × 6 politiques × 10 graines.
- À 5 % de budget, MIRSAD + exploration (ε = 0,2) capture **44,9 % ± 2,5** du revenu récupérable, contre **5,4 %** au hasard
  (≈ 8×) et **39,0 %** pour les règles. MIRSAD ε = 0 : 36,0 % ± 12,7.
- Précision@5 % : 42,9 % (ε = 0,2), contre 9,6 % au hasard.
- Fraudes historiques : MIRSAD ε = 0 capture 14,0 %, contre 10,6 % pour les règles (+32 %). À 10 % : 31,2 % contre 23,4 %.
- **Exploration** : à 5 %, ε = 0,2 fait passer la capture du schéma de 58,3 % ± 27,2 à 78,0 % ± 5,0 (Welch p = 0,049 ;
  variance, Levene p = 0,043), et **la pire graine de 5,6 % à 67,8 %**. Ce sont 2 tests sur 16 : ils ne résistent pas à une
  correction pour comparaisons multiples. Robuste à 5 % comme à 10 % : **l'exploration améliore le pire cas**. À dire ainsi :
  « l'exploration réduit le risque de passer à côté d'un nouveau schéma ».

## 3. Le cycle, brique par brique (`results/cycle/*`, 180 exécutions + 30 post-hoc)
Revenu@5 % (total), moyenne ± écart-type :

| Configuration | Sociétés écrans | Réseau | Établies qui dérivent |
|---|---|---|---|
| Aléatoire | 5,4 % | 4,8 % | 4,9 % |
| Règles | 39,0 % ± 0,6 | 47,6 % ± 0,6 | 10,1 % ± 0,1 |
| ④ seul | 36,0 % ± 12,7 | 36,0 % ± 19,2 | **24,7 % ± 5,9** |
| Cycle complet A3 (pré-enregistré) | 40,0 % ± 11,7 | 48,8 % ± 13,9 | 18,0 % ± 7,0 |
| Variante A3b (post-hoc) | **44,0 % ± 3,2** | **53,2 % ± 1,3** | 19,3 % ± 4,8 |

Lecture honnête :
- **Cycle complet A3 contre ④ seul** : pas de différence significative sur les sociétés écrans et le réseau. Sur le réseau,
  la capture du schéma passe de 56,6 % à 84,3 % (p = 0,10, non sig.). **Perte significative sur les entreprises établies qui
  dérivent** (18,0 % contre 24,7 %, p = 0,03). C'est le coût de la facilitation : on fait moins de contrôles chez les
  entreprises « Confiance », or ce sont elles qui fraudent dans ce schéma.
- **A3 contre règles** : égalité (sociétés écrans, réseau), mieux sur les établies (18,0 % contre 10,1 %, p = 0,006).
- **Variante post-hoc A3b** : elle bat les règles sur les **trois** schémas (p ≤ 0,0006) et ④ seul sur le réseau
  (53,2 % contre 36,0 %, p = 0,02), avec une variabilité très faible (± 1 à 5 points). Elle reste moins bonne que ④ seul sur
  les entreprises établies (p = 0,04). Conçue après les résultats : **à confirmer**.
- **Calibration** : le cycle rend les probabilités plus fiables. Score de Brier 0,076 contre 0,100 pour ④ seul
  (p ≤ 0,002 sur les trois schémas). Les audits aléatoires et l'exploration donnent au modèle des étiquettes moins biaisées.
- **② score entreprise** : utilisé seul comme variable du modèle (A1), il n'apporte pas de gain significatif (+2,3 ; −3,0 ;
  −2,8 points). Sa moyenne a posteriori reprend l'information des profils lissés. Sa valeur est ailleurs : incertitude,
  tendance, segmentation, explication.

## 4. ③ Segments (`results/cycle/segments.csv`, cycle complet)
- Taux de fraude réel par palier (schéma « sociétés écrans ») : **Confiance 2,0 % < Standard 2,3 % < Surveillé 8,7 % <
  Critique 84 %**. L'ordre est cohérent sur les trois schémas.
- **Surveillé = 93 % du volume** : avec 5 % de contrôles, la plupart des entreprises sont simplement « peu connues ». C'est
  une propriété réelle des étiquettes sélectives. Une segmentation fine demande plus de contrôles, ou des données
  externes (registre, fiscalité : T7).

## 5. ⑦ Détecteur de tendances (`results/cycle/detector.json`)
- Sociétés écrans : alerte « nouveaux opérateurs » (chapitre 87) dès la **semaine 26, celle du début du schéma**.
- Réseau : alertes « éventail du déclarant » et « nouveaux opérateurs » dès la **semaine 26**.
- Entreprises établies qui dérivent : **aucune alerte** (le détecteur ne voit pas ce schéma).
- **0 fausse alerte** sur les données sans schéma, 0 alerte avant la semaine 26.
- Limite : les signaux ont été conçus en connaissant le motif « nouvelles entreprises ». La détection sur les schémas
  sociétés écrans et réseau est donc en partie circulaire.

## 6. ⑤ Agent d'enquête (`results/dossiers/index.json`)
- Chaîne de fournisseurs (démo) : API OpenAI gpt-4.1 → LLM local Qwen3 8B (Ollama) → gabarit déterministe. Chaque dossier
  passe le validateur : preuves, nombres, citations verbatim, voie inchangée, cohérence hypothèse/preuve, base légale
  exigée si des extraits pertinents ont été trouvés.
- **26/26 dossiers validés** (semaine de démo) : 20 par l'API du premier coup, 5 après une correction, 1 rattrapé par le LLM
  local après deux rejets de l'API. **26/26 citent une base légale vérifiée mot pour mot**, contre 3/26 avant la règle du
  validateur qui exige une citation quand des extraits pertinents existent. Durée médiane : 12,4 s par dossier.
- Mesures du LLM local (RTX 4060 Laptop 8 Go) : 26/26 dossiers validés, médiane de 31 s, avec un contexte de 8k. À 12k, le
  cache déborde en mémoire partagée : lecture du prompt 1 744 → 209 jetons/s.
- Exemple de garde-fou : le LLM local a inventé des références juridiques (« REG-2024-001 ») ; le validateur les a rejetées.

## 7. Espèce T18, signal de ① (`results/espece_metrics_*.json`, jeu de 50 descriptions construit par l'équipe, optimiste)
| Mode | Top-1 SH6 | Top-3 SH6 | Alertes : précision / rappel | Injections |
|---|---|---|---|---|
| BM25 seul | 56 % | 90 % | 67 % / 55 % | 3/3 |
| + reclassement LLM local | 80 % | 94 % | 73 % / 73 % | 3/3 |
| + reclassement API | 98 % | 100 % | 100 % / 64 % | 3/3 |

## 8. Miroir et base légale
- Miroir UN Comtrade 2024, Tunisie × 7 partenaires (SH2) : indicateur de priorisation, pas une preuve.
- Corpus juridique verbatim : Accord OMC sur l'évaluation en douane, Kyoto révisée ch. 6, Code des douanes art. 43–64.

## Interdits
Gains en dinars réels ; affirmations sur le fonctionnement interne du système de la Douane ; critique du système existant ;
tout chiffre non produit par notre code ; tout article absent du corpus ; présenter A3b comme pré-enregistré ; présenter
une différence non significative comme un gain.
