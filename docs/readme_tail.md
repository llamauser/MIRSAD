## Limites (à lire)
- **Données synthétiques** (BACUDA) : pays, importateurs et bureaux anonymisés, montants non réalistes et devise inconnue
  (affichés « TND simulés »). Tous les gains sont **relatifs** à des références (aléatoire, règles) **à budget égal**.
- **Scénario de fraude injecté** par l'équipe (`src/mirsad/drift.py`, `results/drift_log.json`). Un seul ajustement
  (part 15 % → 5 %), fait avant tout résultat et documenté dans `docs/decisions.md`.
- **Exploration** : aucune différence de moyenne significative (test de Welch, 10 graines). Elle améliore le pire cas
  sur le schéma injecté à 5–10 % de budget (voir `docs/facts_for_pitch.md`, § 5).
- **Espèce** : jeu de 50 descriptions construit par l'équipe, glossaire FR→EN rédigé par la même équipe (évaluation
  optimiste) ; taux de droits **illustratifs**.
- **Miroir** : indicateur de priorisation, pas une preuve (régimes suspensifs, entreprises totalement exportatrices,
  décalages temporels, transit, CIF/FOB, classement).
- **Agent LLM** : le modèle local (8B) est plus lent (plusieurs minutes par dossier sur un GPU portable) et moins fin
  que l'API. Le validateur garantit l'ancrage (preuves, nombres, citations), pas la finesse du raisonnement. Chaque
  dossier indique le fournisseur utilisé (local, API ou gabarit).
- **Base légale** : trois textes publics chargés (extraits). Le Code des douanes n'est présent que pour ses articles
  43 à 64 : la version intégrale accessible (WIPO Lex / Africa-laws) a un encodage de police défectueux, et nous ne
  « réparons » pas un texte juridique. MIRSAD ne génère jamais d'article de loi : toute citation est vérifiée mot pour mot.

## Recommandations pour une mise en production
- **Souveraineté des données** : c'est déjà le mode par défaut du prototype. Le LLM open-weight (Qwen3 8B, licence
  Apache 2.0) tourne **sur site** via Ollama, et l'API externe n'est qu'un secours désactivable (`config.yaml` →
  `llm.api.enabled: false`). En production : API désactivée, serveur GPU interne, dans le respect de la loi organique
  n° 2004-63 sur la protection des données personnelles et sous le contrôle de l'INPDP.
- **Humain dans la boucle** : l'agent des douanes décide ; ses décisions (« fraude confirmée » / « conforme ») alimentent
  les profils de risque et le réentraînement.
- **Suivi de dérive** : taux de fraude par voie, part de faux-verts mesurée par contrôles aléatoires de référence,
  alertes sur les nouveaux importateurs.
- **Intégration** : couche complémentaire à côté du système de sélectivité existant (la Douane a annoncé en mai 2026
  l'intégration d'un module d'apprentissage automatique dans le système national de sélectivité : Directinfo,
  Tuniscope, Réalités), sans le remplacer.

## Sources, bibliothèques et API
**Données**
- Jeu de déclarations synthétiques **BACUDA / Seondong « Customs-Fraud-Detection »** (Institute for Basic Science,
  projet BACUDA de l'OMD), licence **MIT** : https://github.com/Seondong/Customs-Fraud-Detection
  (fichier `data/synthetic-imports-declarations.csv`, commit `0314b92d`).
- **UN Comtrade** (Nations unies), via le package officiel **`comtradeapicall`** : https://comtradeplus.un.org/ ;
  https://pypi.org/project/comtradeapicall/
- **Système harmonisé 2022** : dépôt `datasets/harmonized-system` (licence **ODC-PDDL-1.0**, source UN Comtrade) :
  https://github.com/datasets/harmonized-system
- Jeu de démonstration « espèce » (`data/espece/demo_set.csv`) et description du cas d'injection : **construits par
  l'équipe** ; ils ne décrivent aucune expédition réelle.

**Travaux qui ont inspiré l'approche** (idées uniquement, code non réutilisé)
- S. Kim et al., « DATE: Dual Attentive Tree-aware Embedding for Customs Fraud Detection », KDD 2020.
- Travaux d'apprentissage actif / exploration pour le ciblage douanier sur le même dépôt BACUDA (stratégies de
  requête hybrides exploitation / exploration), voir le dossier `query_strategies` et `literatures` du dépôt Seondong.

**Textes juridiques** (`data/legal/`, extraits verbatim, chaque fichier commence par sa ligne `SOURCE:`)
- OMC, Accord sur la mise en œuvre de l'article VII du GATT de 1994 (évaluation en douane), texte français :
  https://www.wto.org/french/docs_f/legal_f/20-val_01_f.htm (le site précise que les textes reproduits n'ont pas le
  statut juridique des originaux).
- OMD, Convention de Kyoto révisée, Annexe générale, chapitre 6 « Contrôle douanier » :
  https://www.wcoomd.org/fr/topics/facilitation/instrument-and-tools/conventions/pf_revised_kyoto_conv/kyoto_new/gach6.aspx
- Code des douanes tunisien (loi n° 2008-34 du 2 juin 2008), articles 43 à 64, extrait publié par la base DCAF
  « La législation du secteur de la sécurité en Tunisie » : https://legislation-securite.tn/
  (aucun système d'information de l'administration tunisienne n'a été interrogé).

**Modèles et API**
- **LLM local (par défaut)** : Qwen3 8B (Alibaba Qwen, licence Apache 2.0, quantification Q4_K_M) servi par **Ollama**
  (https://ollama.com), variante `mirsad-qwen3:8b` avec un contexte de 16k (`ollama/Modelfile`).
- **Secours** : OpenAI API (Chat Completions, function calling, structured outputs) : `gpt-4.1` pour l'agent,
  `gpt-4.1-mini` pour le reclassement SH. Clés lues depuis `.env` (non versionné).

**Bibliothèques Python**
pandas, numpy, scikit-learn (IsolationForest, IsotonicRegression, métriques), LightGBM, SHAP, networkx, rank_bm25,
Streamlit, Plotly, matplotlib, openai (client aussi utilisé pour l'API compatible d'Ollama), comtradeapicall, pyarrow,
PyYAML, joblib, scipy (test de Welch), pypdf (extraction du texte juridique), pytest.

**Annonce publique citée** : intégration d'un module d'apprentissage automatique dans le système national de
sélectivité, annoncée par la Douane tunisienne en mai 2026 (Directinfo, Tuniscope, Réalités).

---
## English summary
MIRSAD is a customs-targeting copilot built overnight for the Tunisian national hackathon on AI & public finance. It
scores each import declaration (calibrated LightGBM P(fraud) × expected recovered revenue) and assigns red / orange /
green lanes under a fixed inspection budget. Its value is measured in a **leakage-free weekly simulation with
selective labels**: only inspected declarations ever reveal their outcome, and an injected new fraud scheme starts at
week 26. For each red case, a tool-calling LLM agent gathers evidence and writes a French case file. A validator
rejects any evidence id, number or legal quote that is not in the tool outputs, and any change of lane; on failure the
system tries the next provider: a local open-weight LLM (Qwen3 8B via Ollama) first, then the OpenAI API, then a
deterministic template. A UN Comtrade mirror-statistics module (real Tunisia 2024 data) and an
HS-classification check (T18) complete the prototype. All results are on synthetic data and relative to baselines at
equal budget.
