# Decisions log

- **Dataset source**: `raw.githubusercontent.com/.../main/...` returned 404; the default branch is `master` (commit 0314b92d). Config now uses `master`; clone fallback kept.
- **Week index**: week = floor((date − 2013-01-02)/7) + 1 → weeks 1..52.
- **Value features use all past declarations** (declared values are observed without inspection); **labels** (risk profiles, model training) use only past *inspected* rows. Static features for week w use weeks < w only.
- **Drift share 0.15 → 0.05 (the single scenario adjustment, made BEFORE any simulation result)**: with 0.15, the injected rows (taxes lost = 60% of declared taxes, heavy-tailed) totalled 24.9M simulated TND, i.e. 3× the revenue of *all* historical frauds of the year (8.27M). The headline metric would then only measure the injected scheme. With 0.05 the scheme is of the same order as the historical frauds. Metrics are reported split (historical vs injected).
- **Calibration**: isotonic on the most recent revealed week, only when it has ≥30 rows with both classes (else raw LightGBM scores); the classifier is then trained on the other revealed weeks.
- **Sanity split** risk profiles: training rows get the prior only (no in-sample target encoding).
- **Seeds 3 → 10**: the first 3-seed grid showed bimodal outcomes on the injected scheme (either locked-on within a few weeks or missed entirely: e.g. MIRSAD ε=0.1, r=5%: 0.77 / 0.58 / 0.00). 3 seeds cannot estimate that; we increased measurement to seeds 0–9. No method or scenario parameter was changed.
- **Naming (fixed at 01:25)**: there is one MIRSAD policy, `mirsad`, ranking by expected recovered revenue ER = P × R̂; ε = 0 is pure ER ranking, ε > 0 adds exploration. (An earlier version called the ε = 0 case `model_er`, which made pitch material call two different things « MIRSAD ». The grid was rerun under the new names.) `model_p` is an ablation (probability only).
- **Operating point ε = 0** for the demo week and KPIs: best mean Revenue@5 % in the grid; exploration is kept as a setting because it did not show a significant gain (see facts_for_pitch.md).
- **Dossiers**: top 20 red cases by ER of demo week 40 (all from the injected scheme in seed 0) + the 5 best-ranked red cases not from the scheme (variety) + 1 injection demo case (team-built description).
- **Mirror (Phase 5)**: preview API (no key) → HS2 level, year 2024 for all pairs available. Libya: no partner-reported exports to Tunisia for 2024/2023 → excluded (recorded in `results/mirror_meta.json`). Flows < 1 M USD on either side dropped. The largest positive gaps (FR/IT/DE ch. 85, 60, 84) are consistent with offshore / inward-processing regimes (entreprises totalement exportatrices, admission temporaire) and must never be presented as fraud: indicator for prioritisation only.
- **LLM providers (01:40)**: local first, API as fallback. Machine: i5-13500H, 32 GB RAM, RTX 4060 Laptop 8 GB, 14 GB
  free disk, so no download. Already installed and chosen: `qwen3:8b` (Q4_K_M, 4.9 GB, native tool calling, good
  French, Apache 2.0). Rejected: `qwen3-coder:30b-a3b` (17 GB, does not fit 8 GB VRAM, coder-tuned) and `llama3.1:8b`
  (weaker French). Variant `mirsad-qwen3:8b` first used num_ctx 16384 (an investigation used ~7–11k tokens; the default
  context would truncate silently); see the 8k decision below. Server started with `OLLAMA_FLASH_ATTENTION=1`, `OLLAMA_KV_CACHE_TYPE=q8_0` → 100 % GPU.
  Qwen3 thinking disabled via `reasoning_effort: none` on the OpenAI-compatible endpoint (`think: false` was ignored there).
  API fallback `gpt-4.1` (supports temperature 0; the GPT-5 family does not). Local time budget 420 s per investigation.
- **Observed local behaviour**: 4–6.5 min per dossier; once invented legal ids (`REG-2024-001`), caught by the validator →
  API fallback. Added a semantic guard (hypothesis type ↔ compatible evidence) after the local model labelled network
  evidence as « fausse origine ».
- **Legal corpus**: only public texts from non-Tunisian-administration hosts (WTO, WCO, DCAF legislation-securite.tn).
  The full Code des douanes PDF (WIPO Lex / Africa-laws edition) has broken glyph mappings (letters missing after text
  extraction with both pypdf and pdfminer) → not used, rather than "repairing" legal text. The JORT link hosted on
  cnudst.rnrt.tn (Tunisian public server) was deliberately not fetched. Legal search results expose verbatim
  `phrases_citables`; the validator checks quotes against the full chunk text in the corpus.
- **Keys**: `.env` (gitignored) with 4 keys rotated on auth/rate-limit errors; never printed (masked in logs).
- **Local context 16k → 8k (02:10)**: measured with Ollama's own timings on the RTX 4060 Laptop, same 6.8k-token
  prompt: num_ctx 8192 → prompt 1744 tok/s, generation 36 tok/s; num_ctx 12288 → prompt 209 tok/s (KV/compute buffers
  spill to shared system memory under Windows). At 16k with ~12k tokens: prompt 127 tok/s, generation 5.5 tok/s. So:
  num_ctx 8192, compact tool outputs (legal: ≤4 chunks × ≤4 quotable sentences, no HS labels when legal text matches;
  links: top 3), compact JSON skeleton instead of the full schema, and a context guard (stop gathering at 70 %, hand
  over to the API above 88 %). Result: local investigation 160–390 s → ~45 s. Local dossiers use plain JSON mode
  (`json_object`); the validator enforces the schema (fields, enums, types).
- **Chunking** now cuts on word boundaries, and quotable sentences drop fragments cut by the window (a quote once started
  mid-word: « océder à la visite… »).
- **API as main LLM (05:00, team request)**: `llm.order: [api, local]`. The local model was too heavy for the demo
  machine; it stays as a fallback and as the production recommendation (on-premises). Local measurements are kept.
- **Calibration isotonic → Platt (04:30)**: isotonic calibration on the most recent inspected week produced 0.9999
  plateaus; Platt scaling is smooth and bounded (clip 0.001–0.98). Probabilities remain selection-biased (fitted on
  inspected rows only). This changed the main grid: at 5 %, MIRSAD ε=0 now 36.0 % (was 39.9 %), ε=0.2 44.9 % ± 2.5.
- **Risk cycle (04:25–05:05)**: stages ②③⑦ added. Thresholds (entity, cycle, trends) committed in git BEFORE the
  evaluation (commit "Cycle scaffolding…"). Pre-registered full loop = `cycle_A3`.
- **Post-hoc variant `cycle_A3b` (05:05)**: after seeing that `cycle_A3` loses to ④ alone on the turncoat scheme
  (p = 0.03), we tested keeping « Confiance » companies eligible for exploitation. It is reported separately and flagged
  as post-hoc in the app and docs; the demo register still uses the pre-registered `cycle_A3`.
- **Detector honesty**: signals were designed knowing the "new front companies" pattern, so detection on front/network is
  partly circular; it is blind to the turncoat scheme (0 alerts); 0 false alarms on the scheme-free data.
