# Decisions log

- **Dataset source**: `raw.githubusercontent.com/.../main/...` returned 404; the default branch is `master` (commit 0314b92d). Config now uses `master`; clone fallback kept.
- **Week index**: week = floor((date − 2013-01-02)/7) + 1 → weeks 1..52.
- **Value features use all past declarations** (declared values are observed without inspection); **labels** (risk profiles, model training) use only past *inspected* rows. Static features for week w use weeks < w only.
- **Drift share 0.15 → 0.05 (the single scenario adjustment, made BEFORE any simulation result)**: with 0.15, the injected rows (taxes lost = 60% of declared taxes, heavy-tailed) totalled 24.9M simulated TND, i.e. 3× the revenue of *all* historical frauds of the year (8.27M). The headline metric would then only measure the injected scheme. With 0.05 the scheme is of the same order as the historical frauds. Metrics are reported split (historical vs injected).
- **Calibration**: isotonic on the most recent revealed week, only when it has ≥30 rows with both classes (else raw LightGBM scores); the classifier is then trained on the other revealed weeks.
- **Sanity split** risk profiles: training rows get the prior only (no in-sample target encoding).
- **Seeds 3 → 10**: the first 3-seed grid showed bimodal outcomes on the injected scheme (either locked-on within a few weeks or missed entirely: e.g. MIRSAD ε=0.1, r=5%: 0.77 / 0.58 / 0.00). 3 seeds cannot estimate that; we increased measurement to seeds 0–9. No method or scenario parameter was changed.
- **ε = 0 is `model_er`** (identical code path), so the mirsad grid only runs ε ∈ {0.1, 0.2}.
- **Dossiers**: top 20 red cases by ER of demo week 40 (all from the injected scheme in seed 0) + the 5 best-ranked red cases not from the scheme (variety) + 1 injection demo case (team-built description).
- **Mirror (Phase 5)**: preview API (no key) → HS2 level, year 2024 for all pairs available. Libya: no partner-reported exports to Tunisia for 2024/2023 → excluded (recorded in `results/mirror_meta.json`). Flows < 1 M USD on either side dropped. The largest positive gaps (FR/IT/DE ch. 85, 60, 84) are consistent with offshore / inward-processing regimes (entreprises totalement exportatrices, admission temporaire) and must never be presented as fraud: indicator for prioritisation only.
