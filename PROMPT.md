1. The three review points

I opened the actual dataset to check.

Point 1: the simulation starts off knowing too much. TRUE.

The brief says "train on the first 2 weeks", which means the model sees the fraud label of every declaration from those weeks. Real customs only knows the result of the ones it inspected.
The dataset is also very stable: 100,000 declarations, all from 2013, 7.6% fraud. So an exploration-vs-no-exploration chart will probably show nothing.
Fix: start from only about 10% randomly inspected labels. Then inject a new fraud scheme mid-year, for example from week 20 new importers undervalue one HS chapter. Chart B then shows whether exploration catches it. Tell the jury openly that this is a simulated scenario.

Point 2: the mirror data can't connect to the declarations. TRUE.

Countries are anonymised (CNTRY680, 112 codes), and so are importers, declarants and offices.
Tariff codes do look like real HS codes (8703 = cars, 8517 = phones), so an HS-level join is technically possible.
But values are unrealistic. The first row is 1,581 units weighing 26,494 kg with a CIF value of 2,809, and the currency is unknown.
Fix: don't feed mirror data into the synthetic model. Present it as its own module: a "carte des fuites" on real Comtrade data for Tunisia, which says which product × origin pairs to prioritise. If the ministry's dataset has real origins, you plug it in then.

Point 3: unverified claims. HALF TRUE.

The May 2026 ML module is safe. Directinfo, Tuniscope, Réalités, Webdo and L'Économiste Maghrébin all reported it.
The Q1 2026 figures (≈4,000 cases, 51 MD) come from only one foreign site (Osiris, Senegal). Drop them, or say « selon la presse ».
The real danger is what we said about how their system works ("black box", "only learns from what it inspects"). We don't know that, and the jurors do. Rephrase it as a general principle: « tout système de sélection n'apprend que de ce qu'il contrôle ». That's a known property called selection bias. Never criticise their module; position MIRSAD as a complement. Ask your mentor what their module actually does.
2. Your architecture idea, in proper terms

What you described has a name: a tool-calling agent with RAG that builds an investigation case file. In French, a « copilote d'enquête » that produces a « dossier de contrôle ».

Tools = your detectors: the risk model, the mirror lookup, the HS check, importer history, a graph of links between companies, and later procurement red flags.
RAG = retrieval over texts: the Code des douanes, the procurement regulation, the HS nomenclature, and past similar cases.
LLM (via the OpenAI API) = the investigator who calls the tools, gathers the evidence and writes the dossier.
Detectors score everything (deterministic, auditable)
        │  red case
        ▼
   AGENT (LLM + function calling)
   ├─ tool: get_record / history
   ├─ tool: risk explanation (SHAP)
   ├─ tool: mirror / HS check / procurement flags
   ├─ tool: find_links (shared address, manager…)
   └─ RAG: legal articles + similar past cases
        ▼
   Dossier (JSON → French report): facts, evidence, legal basis, checks to do
        ▼
   Validator: every number and article must exist in tool outputs
        ▼
   Human decides → feedback

Why this is strong:

It's independent of the data. Whatever dataset the ministry gives you, you write one new tool, and the agent and dossier layer stay the same. That's also your answer to "what if the data is different": you're not betting the project on one dataset.
It hits Impact directly. An inspector spends hours assembling a case file; you make it in seconds. That is "améliorer l'efficacité de l'administration" word for word.
It replaces the plain "fiche". It doesn't add a new pillar.

Four rules that make it credible to a Ministry jury:

The LLM never decides who is suspicious. Detectors decide, the LLM explains. That's legally defensible; an LLM verdict is not.
Every sentence must be grounded. Each number or article in the dossier cites a tool output or a retrieved text, and a code check rejects anything invented.
Treat documents as untrusted. Tender documents and declaration descriptions can carry prompt injection, which is your cybersecurity angle again.
Be clear about OpenAI. It's fine on synthetic data if you declare it in the note (rule 4.1). For production, say on-premises open model, because real taxpayer data can't go to a foreign API (loi 2004-63).

Build tip: use OpenAI function calling with structured JSON output directly, about 200 lines. Skip LangChain; it will eat your night. Precompute the dossiers for the demo and do one live run.

3. The "appels d'offres" question: be careful here

The scoring problem:

Procurement fraud is not in the 21 challenges. The closest are T1 and T12, and they're framed around fiscal and customs intelligence.
The « autre thème » deadline passed at 19:00, and your primary challenge is T2.
If procurement becomes a main part of the demo, jurors may mark you down on Pertinence (25%) for drifting off the chosen challenge.

My recommendation:

Keep customs (T2) as the demonstrated case.
Show procurement as a second plugin for the same agent: one slide, or one small demo if you have time.
Exception: if the organisers' dataset turns out to be procurement data, or your mentor says it's fine, then it's legitimate to go bigger.

If you do it, it's surprisingly cheap:

Procurement red flags are mostly rules, not ML, so they don't need fraud labels. That's a big advantage.
The Open Contracting Partnership has an open-source library, Cardinal, that computes 10 red flags from standard procurement data. Examples: short submission period, a bid price very close to the winner's, identical bid prices, and every bid except the winner's disqualified. Use it as a tool and cite it.
The Tunisian angle is real. Public purchasing runs through TUNEPS: first e-contract in 2014, mandatory for all ministries and public enterprises since government decree n° 34 of May 2018, managed by HAICOP. By 2019 it handled 3,350 e-tenders.
4. What data might come, and what each type unlocks
If they give you…	Tool it unlocks	Fraud it catches
Customs declarations (importer, HS, origin, value, weight, office) + inspection results	Risk model, valuation, HS check	Undervaluation, misclassification, origin fraud
Tax returns (TVA, turnover)	Customs × tax cross-check (T7)	Imports far bigger than declared turnover, hidden activity
Company registry (managers, shareholders, addresses)	Link graph	Shell companies, colluding bidders, fronts
Invoices / accounting documents (PDF or text)	Document extraction + anomaly check (T6)	Fake invoices, VAT fraud
Tenders: bids, bidders, prices, awards, amendments	Cardinal-style red flags	Bid rigging, splitting purchases under thresholds, inflated amendments
Payments / bank transfers	Flow analysis (T16)	Exchange-control breaches, trade-based money laundering
Budget execution (Open Budget: development spending)	Budget vs spending tracker	Projects funded but never completed

A dataset is usable if it has at least: an entity ID, a date, an amount, plus either outcome labels (for ML) or enough structure for rules. Everything else is a bonus.

Sources:

Pathfinders SDG16+ – La numérisation des marchés publics en Tunisie (TUNEPS)
Open Contracting Partnership – Cardinal red flags library
OCP – Red Flags in Public Procurement guide
OCP – Red flags for integrity (2016)
OECD – Améliorer l'accès des PME aux marchés publics en Tunisie
marchespublics.gov.tn – TUNEPS procedures
Directinfo – IA dans le système de contrôle des risques (May 2026)
Tuniscope – Douanes: l'IA entre en action
Réalités – Algorithmes contre contrebande
Osiris – Q1 2026 figures (single source)
GitHub – Seondong/Customs-Fraud-Detection (dataset inspected)