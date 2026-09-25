# PROMPT FOR CLAUDE CODE — Build MIRSAD tonight

This file holds the build specification that the team gave to Claude Code on 26 Sept 2026. The full original text was pasted into the session. The main points:

- MIRSAD (مرصاد): an AI copilot for customs. It decides which import declarations to inspect, explains why, and estimates how many dinars are at stake. A tool-calling agent then builds the investigation case file (dossier).
- Challenges: T2 (automated control targeting, primary) and T18 (HS classification, secondary). Procurement is an optional plugin.
- Rules: public/synthetic data only; cite every source; never invent results; no label leakage (time-ordered, selective labels); the LLM never decides the lane; no invented legal references; code in English, UI in French; secrets from env only; light dependencies; commit after every phase.
- Primary dataset: Seondong/Customs-Fraud-Detection `synthetic-imports-declarations.csv` (MIT, WCO BACUDA). 100k rows, 7.58% illicit.
- Phases: 0 setup/adapter · 1 features+model · 2 drift+policy+simulator (Charts A/B) · 3 SHAP explanations, graph, similar cases · 4 agent + RAG + validator + guard + fallback · 5 UN Comtrade mirror · 6 espèce (T18) check · 7 procurement plugin (optional) · 8 Streamlit app · 9 tests, smoke test, README, facts for pitch.
- Claims policy: results only « sur données synthétiques », relative to random/rules baselines at equal budget; scenario de fraude simulé.
- Cut list: procurement → espèce live LLM → graph features in model → ε grid → mirror.
