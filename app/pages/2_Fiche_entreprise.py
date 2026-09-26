import numpy as np
import plotly.graph_objects as go
import streamlit as st

from common import fr, load_parquet, page
from mirsad.entity import segment

page("Fiche entreprise")
st.title("② ③ Fiche entreprise : score dynamique et segment")
st.markdown("Le score est une **loi bêta a posteriori** du taux de fraude de l'entreprise. Il part du taux observé lors "
            "des contrôles *aléatoires* et se met à jour à chaque contrôle révélé, avec une demi-vie de 12 semaines. "
            "L'incertitude compte autant que le score : une entreprise peu connue est « Surveillée », pas "
            "« Confiance ». Tout est calculé à la date de la semaine, sans information future.")

comp = load_parquet("data/processed/company_scores.parquet")
reg = load_parquet("data/processed/risk_register.parquet")
if comp is None or reg is None:
    st.error("Registre de risque absent : lancer `scripts/07_cycle_experiments.py`.")
    st.stop()
week = int(comp.week.max())
cur = comp[comp.week == week].set_index("importer")
p0 = float(cur[cur.ent_neff == 0].ent_mean.median()) if (cur.ent_neff == 0).any() else 0.076

demo = reg[(reg.week == week) & (reg.lane == "Rouge")].sort_values("er", ascending=False)
default = demo.importer.iloc[0] if len(demo) else cur.index[0]
opts = list(dict.fromkeys([default] + demo.importer.head(30).tolist() +
                          cur.sort_values("ent_mean", ascending=False).head(30).index.tolist()))
c0, c1 = st.columns([2, 1])
imp = c0.selectbox("Entreprise (importateur)", opts, index=0)
other = c1.text_input("…ou saisir un identifiant", "")
if other.strip() and other.strip() in cur.index:
    imp = other.strip()
if imp not in cur.index:
    st.warning("Entreprise inconnue à cette date.")
    st.stop()
row = cur.loc[imp]

# ⑥ feedback loop: decisions taken in this session update the posterior (a += fraude, b += conforme)
fb = st.session_state.setdefault("feedback", {}).setdefault(imp, {"fraude": 0, "conforme": 0})
a, b = row.ent_a + fb["fraude"], row.ent_b + fb["conforme"]
mean = a / (a + b)
sd = np.sqrt(a * b / ((a + b) ** 2 * (a + b + 1)))
neff = row.ent_neff + fb["fraude"] + fb["conforme"]
seg = segment([mean], [neff], p0)[0]
changed = fb["fraude"] or fb["conforme"]

SEG_COL = {"Critique": "#c0392b", "Surveillé": "#d9822b", "Standard": "#52514e", "Confiance": "#1e8449"}
k = st.columns(5)
k[0].metric("Score de risque (0–100)", fr(100 * mean, 1),
            delta=f"{fr(100 * (mean - row.ent_mean), 1)} pts (décisions de la session)" if changed else None,
            delta_color="inverse")
k[1].metric("Intervalle à 90 %", f"{fr(100 * max(0, mean - 1.645 * sd), 1)} – {fr(100 * min(1, mean + 1.645 * sd), 1)}")
k[2].metric("Contrôles effectifs", fr(neff, 1))
k[3].metric("Tendance 4 semaines", f"{fr(100 * row.ent_trend, 1)} pts")
k[4].markdown(f"<div style='margin-top:.3rem'>Segment<br><span class='lane' style='background:{SEG_COL[seg]}'>{seg}</span>"
              + (f"<br><small>avant : {row.segment}</small>" if seg != row.segment else "") + "</div>",
              unsafe_allow_html=True)
st.caption(f"Taux de base (contrôles aléatoires) : {fr(100 * p0, 1)} %. Règles de segment : Surveillé si moins de 2 contrôles "
           "effectifs ; Critique si score ≥ 2 × taux de base ; Confiance si score ≤ 0,75 × taux de base.")

h = comp[comp.importer == imp].sort_values("week")
fig = go.Figure()
fig.add_trace(go.Scatter(x=h.week, y=100 * (h.ent_mean + 1.645 * h.ent_sd).clip(upper=1), line=dict(width=0),
                         showlegend=False, hoverinfo="skip"))
fig.add_trace(go.Scatter(x=h.week, y=100 * (h.ent_mean - 1.645 * h.ent_sd).clip(lower=0), fill="tonexty",
                         fillcolor="rgba(42,120,214,0.15)", line=dict(width=0), name="Intervalle à 90 %"))
fig.add_trace(go.Scatter(x=h.week, y=100 * h.ent_mean, line=dict(color="#2a78d6", width=2.5), name="Score"))
fig.add_hline(y=100 * 2 * p0, line_dash="dot", line_color="#c0392b", annotation_text="seuil Critique")
fig.add_hline(y=100 * p0, line_dash="dot", line_color="#8a8984", annotation_text="taux de base")
fig.update_layout(height=320, margin=dict(l=10, r=10, t=10, b=10), xaxis_title="Semaine", yaxis_title="Score (0–100)",
                  plot_bgcolor="#fbfbfa", paper_bgcolor="#fbfbfa", legend=dict(orientation="h", y=-0.3))
st.plotly_chart(fig, width="stretch")

l, r = st.columns(2)
with l:
    st.subheader("Contrôles passés (résultats révélés)")
    past = reg[(reg.importer == imp) & (reg.week < week) & (reg.lane == "Rouge")]
    if len(past):
        st.dataframe(past[["id", "week", "hs6", "selected_by", "label_fraud", "label_revenue"]].rename(columns={
            "id": "Déclaration", "week": "Semaine", "hs6": "SH6", "selected_by": "Motif", "label_fraud": "Fraude",
            "label_revenue": "Redressement (TND)"}), hide_index=True, width="stretch")
    else:
        st.info("Aucun contrôle révélé : l'entreprise est peu connue (score = a priori).")
with r:
    st.subheader("Réseau : déclarants utilisés")
    decl = reg[(reg.importer == imp) & (reg.week <= week)].groupby("declarant").size().sort_values(ascending=False)
    st.dataframe(decl.head(8).rename("Déclarations").reset_index().rename(columns={"declarant": "Déclarant"}),
                 hide_index=True, width="stretch")
    st.caption(f"Risque propagé par le réseau : {fr(100 * row.link_risk, 1)} % (moyenne des scores des déclarants, "
               "pondérée par l'usage).")

st.divider()
st.subheader("⑥ Apprendre : retour de l'agent après contrôle")
bc = st.columns([1, 1, 1, 3])
if bc[0].button("✅ Fraude confirmée"):
    fb["fraude"] += 1
    st.rerun()
if bc[1].button("☑️ Conforme"):
    fb["conforme"] += 1
    st.rerun()
if bc[2].button("↺ Réinitialiser"):
    fb.update({"fraude": 0, "conforme": 0})
    st.rerun()
bc[3].caption("Chaque résultat met à jour la loi bêta (fraude : a + 1, conforme : b + 1). En production, il est écrit "
              "dans le registre de risque et pris en compte au réentraînement de la semaine suivante.")
