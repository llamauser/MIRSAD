import streamlit as st

from common import ROOT, fr, kpi, load_json, metric, page, pct

page("Accueil")
st.title("MIRSAD — le copilote de ciblage douanier")
st.markdown(
    "**Le problème.** Les agents ne peuvent contrôler qu'une petite part des déclarations. Chaque contrôle "
    "mal orienté coûte du temps, et chaque fraude orientée en voie verte coûte des recettes.  \n"
    "**Ce que fait MIRSAD.** Pour chaque déclaration, il estime la probabilité de fraude et le **montant en jeu** "
    "(TND), puis oriente vers Rouge / Orange / Vert sous un budget de contrôle fixé.  \n"
    "**Pour chaque cas rouge,** un agent IA outillé rassemble les preuves et rédige un **dossier d'enquête vérifié** : "
    "chaque fait est relié à sa source, et le LLM ne décide jamais de la voie."
)

m = load_json("results/metrics.json")
if m:
    r = 0.05
    er = metric(m, "mirsad", r, 0.0, "revenue_at_k")
    rnd = metric(m, "random", r, 0.0, "revenue_at_k")
    rules = metric(m, "rules", r, 0.0, "revenue_hist_at_k")
    er_h = metric(m, "mirsad", r, 0.0, "revenue_hist_at_k")
    vert = metric(m, "mirsad", r, 0.0, "share_vert")
    fg = metric(m, "mirsad", r, 0.0, "false_green_rev")
    c = st.columns(4)
    kpi(c[0], pct(er["mean"]), "du revenu récupérable capturé en contrôlant 5 % des déclarations",
        f"MIRSAD (classement par montant en jeu), ± {fr(100 * er['std'], 1)} points sur {len(m['seeds'])} graines")
    kpi(c[1], pct(rnd["mean"]), "avec une sélection aléatoire, au même budget",
        f"soit ≈ {er['mean'] / rnd['mean']:.0f}× plus de recettes pour MIRSAD".replace(".", ","))
    kpi(c[2], f"{pct(er_h['mean'])} vs {pct(rules['mean'])}", "fraudes historiques : MIRSAD vs règles (profil importateur)",
        "revenu capturé, à budget égal (5 %)")
    kpi(c[3], pct(vert["mean"], 0), "des déclarations en voie Verte (dédouanement rapide)",
        f"faux-vert : {pct(fg['mean'])} du revenu récupérable reste en Vert")
    st.caption("Source : `results/metrics.json`, simulation hebdomadaire de 50 semaines avec étiquettes sélectives "
               "(seules les déclarations contrôlées révèlent leur résultat), données synthétiques BACUDA et scénario de "
               "fraude injecté. Comparaisons à budget égal.")

st.subheader("Le cycle de risque MIRSAD")
st.caption("Chaque étape lit la précédente et écrit dans un registre de risque unique. Les étapes suivent le processus de "
           "gestion des risques de l'OMD : identifier → analyser → évaluer et prioriser → traiter → surveiller.")
st.graphviz_chart("""
digraph G {
  rankdir=LR; bgcolor="transparent"; nodesep=0.3; ranksep=0.35;
  node [shape=box, style="rounded,filled", fillcolor="#eef2f6", color="#0b1f3a", fontname="Helvetica", fontsize=10];
  edge [color="#52514e"];
  D [label="① DÉTECTER\nsignaux d'anomalie\nvaleur · poids · tarif · réseau · miroir"];
  C [label="② CONNAÎTRE\nscore dynamique entreprise\n(loi bêta, incertitude)"];
  S [label="③ SEGMENTER\nConfiance · Standard\nSurveillé · Critique"];
  T [label="④ CIBLER ★\nP(fraude) × montant\nbudget par segment", fillcolor="#e6f2f1"];
  I [label="⑤ INSTRUIRE\nagent d'enquête\n+ validateur"];
  A [label="⑥ APPRENDRE\nrésultat du contrôle\n(l'humain décide)"];
  M [label="⑦ SURVEILLER\nsignaux faibles\nnouvelles tendances"];
  R [label="Registre de risque\n(lu et écrit par chaque étape)", shape=cylinder, fillcolor="#fdf1e3"];
  D -> C -> S -> T -> I -> A;
  A -> C [label=" met à jour", style=dashed, constraint=false];
  A -> M [constraint=false];
  M -> T [label=" budget d'exploration", style=dashed, constraint=false];
  {D C S T I A M} -> R [style=dotted, arrowhead=none, color="#b8b8b3"];
}
""")
st.markdown("**Positionnement.** Défi principal : **T2, ciblage et orientation des contrôles** (étape ④). Défi "
            "complémentaire : **T20, score dynamique de conformité des entreprises** (étape ②). Les autres étapes sont des "
            "**briques qui alimentent T2**, pas des défis revendiqués : T6 (anomalies sur les déclarations), T5 "
            "(segmentation), T12 (signaux faibles).")

legal = ROOT / "data/legal/omd_kyoto_revisee_ch6_controle_douanier.txt"
KYOTO = ("La douane a recours à l’analyse des risques pour désigner les personnes et les marchandises à examiner, "
         "y compris les moyens de transport, et l’étendue de cette vérification.")
if legal.exists() and KYOTO in " ".join(legal.read_text(encoding="utf-8").split()):  # quoted only if verbatim in corpus
    st.markdown(f"> « {KYOTO} »  \n> — Convention de Kyoto révisée (OMD), Annexe générale, norme 6.4")

st.info("La Douane tunisienne a annoncé en mai 2026 l'intégration d'un module d'apprentissage automatique dans le "
        "système national de sélectivité (Directinfo, Tuniscope, Réalités). MIRSAD est pensé comme une **couche "
        "complémentaire** : explication, montant en jeu et dossier d'enquête, avec l'agent humain qui décide.")
st.markdown("**Parcours de démonstration :** une alerte de tendance (①⑦) → l'entreprise derrière (②③) → sa déclaration "
            "en Rouge (④) → le dossier vérifié (⑤) → « Fraude confirmée » → le score de l'entreprise monte (⑥).")
