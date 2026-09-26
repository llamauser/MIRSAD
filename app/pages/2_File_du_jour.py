import streamlit as st

from common import LANE_BG, fr, load_json, load_parquet, page

page("File du jour")
b = load_parquet("results/demo_week.parquet")
idx = load_json("results/dossiers/index.json") or []
if b is None:
    st.error("Fichier `results/demo_week.parquet` absent : lancer `scripts/02_simulate.py`.")
    st.stop()
week = int(b.week.iloc[0])
st.title(f"File du jour — semaine {week}")
st.markdown("Déclarations de la semaine, orientées par le scoreur déterministe (budget r = 5 % en Rouge, 5 % en Orange "
            "pour contrôle documentaire, le reste en Vert). Montants en **TND simulés**.")

c = st.columns(4)
bureaux = c[0].multiselect("Bureau", sorted(b.office.unique()), placeholder="Tous les bureaux")
voies = c[1].multiselect("Voie", ["Rouge", "Orange", "Vert"], default=["Rouge", "Orange"])
sh = c[2].text_input("Code SH (préfixe)", "")
only_dossier = c[3].checkbox("Seulement les cas avec dossier", False)

d = b.copy()
if bureaux:
    d = d[d.office.isin(bureaux)]
if voies:
    d = d[d.lane.isin(voies)]
if sh:
    d = d[d.hs10.str.startswith(sh.strip())]
dossier_ids = {i["case_id"] for i in idx}
if only_dossier:
    d = d[d.id.isin(dossier_ids)]
d = d.sort_values("er", ascending=False)

n = {k: int((b.lane == k).sum()) for k in ["Rouge", "Orange", "Vert"]}
k = st.columns(4)
k[0].metric("Déclarations", f"{len(b)}")
k[1].metric("Rouge (contrôle physique)", n["Rouge"])
k[2].metric("Orange (contrôle documentaire)", n["Orange"])
k[3].metric("Vert", n["Vert"])

view = d[["id", "lane", "er", "p", "r_hat", "office", "importer", "declarant", "country", "hs10", "cif", "taxes"]].copy()
view["dossier"] = view.id.map(lambda x: "📁" if x in dossier_ids else "")
view = view.rename(columns={"id": "Déclaration", "lane": "Voie", "er": "Montant en jeu (TND)", "p": "P(fraude)",
                            "r_hat": "Revenu si fraude (TND)", "office": "Bureau", "importer": "Importateur",
                            "declarant": "Déclarant", "country": "Origine", "hs10": "SH10", "cif": "CIF", "taxes": "Taxes",
                            "dossier": "Dossier"})
sty = (view.head(500).style
       .apply(lambda r: [f"background-color:{LANE_BG.get(r['Voie'], '')}"] * len(r), axis=1)
       .format({"Montant en jeu (TND)": lambda x: fr(x, 0), "Revenu si fraude (TND)": lambda x: fr(x, 0),
                "P(fraude)": lambda x: fr(100 * x, 2 if x > 0.99 else 1) + " %", "CIF": lambda x: fr(x, 0), "Taxes": lambda x: fr(x, 0)}))
st.dataframe(sty, width="stretch", height=560, hide_index=True)
st.caption(f"{len(d)} déclarations affichées (500 max). Montant en jeu = P(fraude) × revenu attendu si fraude. "
           "La voie vient du scoreur ; l'agent IA ne peut pas la modifier. Ouvrir un dossier : page « Dossier ».")
