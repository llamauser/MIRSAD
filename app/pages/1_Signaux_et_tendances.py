import plotly.graph_objects as go
import streamlit as st

from common import fr, load_json, load_parquet, page

page("Signaux et tendances")
st.title("① ⑦ Signaux et tendances")
st.markdown("**⑦ Surveiller.** Chaque semaine, un balayage des seules données *déclarées* (sans étiquette de fraude) "
            "cherche trois signaux faibles : (a) afflux de déclarations d'entreprises nouvelles par chapitre SH, "
            "(b) hausse de la part de prix très bas par position SH4, (c) déclarant qui se met à servir beaucoup de "
            "nouvelles entreprises. Une alerte augmente pendant 2 semaines le budget d'exploration sur la zone signalée (④). "
            "Les seuils ont été fixés **avant** l'évaluation.")
al = load_parquet("data/processed/trend_alerts.parquet")
det = load_json("results/cycle/detector.json")
if al is not None and len(al):
    show = al.sort_values("week", ascending=False).rename(columns={
        "signal": "Signal", "cle_type": "Type", "cle": "Clé", "week": "Semaine", "valeur": "Valeur",
        "reference": "Référence (8 sem.)", "z": "z", "alert_id": "Identifiant"})
    st.dataframe(show.style.format({"Valeur": lambda x: fr(x, 2), "Référence (8 sem.)": lambda x: fr(x, 2),
                                    "z": lambda x: fr(x, 1)}), hide_index=True, width="stretch")
else:
    st.info("Aucune alerte de tendance sur la période.")
if det:
    rows = [{"Scénario (simulé)": d["scenario"], "Alertes sur l'année": d["n_alerts"],
             "Délai de détection (semaines)": "—" if d.get("lead_time_weeks") is None else d["lead_time_weeks"],
             "Signaux concordants": ", ".join(d.get("signals_matching", [])) or "aucun"} for d in det]
    st.markdown("**Évaluation du détecteur** (`results/cycle/detector.json`) : délai entre le début du schéma simulé "
                "(semaine 26) et la première alerte qui le vise ; alertes sur les données sans schéma = fausses alertes.")
    st.dataframe(rows, hide_index=True, width="stretch")

st.divider()
st.subheader("① Signal macro : carte des fuites (statistiques miroir)")
st.markdown("Pour chaque chapitre SH et chaque partenaire, on compare **ce que le partenaire déclare avoir exporté "
            "vers la Tunisie** (FOB) à **ce que la Tunisie déclare avoir importé** (CIF ramené en FOB). Un écart "
            "positif persistant désigne un couple chapitre × origine à examiner en priorité.")

m = load_parquet("data/processed/mirror.parquet")
meta = load_json("results/mirror_meta.json") or {}
if m is None or not len(m):
    st.warning("Données miroir indisponibles : le module n'a pas pu interroger UN Comtrade. Aucune donnée n'est inventée.")
    st.stop()

c1, c2 = st.columns([1, 3])
n_ch = c1.slider("Nombre de chapitres affichés", 10, 40, 25)
metric = c1.radio("Couleur", ["Écart positif (USD)", "Écart relatif log(X / M_fob)"], index=1)
parts = sorted(m.partner_fr.unique())
sel = c1.multiselect("Partenaires", parts, default=parts)
d = m[m.partner_fr.isin(sel)]
top = d.groupby("hs2").leak_usd.sum().sort_values(ascending=False).head(n_ch).index
d = d[d.hs2.isin(top)]
desc = d.groupby("hs2").cmdDesc.first().str.slice(0, 45)
val = "leak_usd" if metric.startswith("Écart positif") else "gap_log"
piv = d.pivot_table(index="hs2", columns="partner_fr", values=val).reindex(top)
Mp = d.pivot_table(index="hs2", columns="partner_fr", values="M_fob_usd").reindex(top)
Xp = d.pivot_table(index="hs2", columns="partner_fr", values="X_fob_usd").reindex(top)
labels = [f"{h} · {desc.get(h, '')}" for h in piv.index]
hover = [[f"{labels[i]}<br>{piv.columns[j]}<br>X (partenaire, FOB) : {fr(Xp.iat[i, j] / 1e6, 1)} M USD"
          f"<br>M Tunisie (FOB estimé) : {fr(Mp.iat[i, j] / 1e6, 1)} M USD<br>écart positif : "
          f"{fr(max(0, Xp.iat[i, j] - Mp.iat[i, j]) / 1e6, 1)} M USD" if piv.iat[i, j] == piv.iat[i, j] else "flux absent ou < seuil"
          for j in range(piv.shape[1])] for i in range(piv.shape[0])]
if val == "leak_usd":
    z, scale, zmid, title = piv.values / 1e6, [[0, "#f3f6f9"], [1, "#0b3d91"]], None, "M USD"
else:
    z, scale, zmid, title = piv.values, [[0, "#b35806"], [0.5, "#f1f1ef"], [1, "#0b3d91"]], 0, "log(X/M)"
fig = go.Figure(go.Heatmap(z=z, x=list(piv.columns), y=labels, colorscale=scale, zmid=zmid, xgap=2, ygap=2,
                           hoverinfo="text", text=hover, colorbar=dict(title=title)))
fig.update_layout(height=max(420, 26 * len(labels)), margin=dict(l=10, r=10, t=10, b=10),
                  yaxis=dict(autorange="reversed"), plot_bgcolor="#fbfbfa", paper_bgcolor="#fbfbfa")
c2.plotly_chart(fig, width="stretch")

st.markdown(f"""<div class="caveat"><b>Indicateur de priorisation, pas une preuve.</b> Les écarts miroir s'expliquent
aussi par : les <b>régimes économiques</b> (entreprises totalement exportatrices, admission temporaire / perfectionnement
actif), le <b>décalage temporel</b> entre expédition et arrivée, le <b>transit et les réexportations</b> (pays de
provenance ≠ pays d'origine), la conversion <b>CIF/FOB</b> (hypothèse forfaitaire c = {fr(100 * meta.get('c_cif_fob', 0.07), 0)} %)
et les <b>différences de classement</b> SH entre pays. Un écart ne vise aucun opérateur : il aide à choisir où regarder.</div>""",
            unsafe_allow_html=True)
st.caption(f"Source : UN Comtrade (package officiel `comtradeapicall`, mode {meta.get('mode', '?')}), déclarant Tunisie (788). "
           f"Années : {meta.get('paires', {})}. Flux < {fr(meta.get('seuil_usd', 1e6) / 1e6, 0)} M USD d'un côté ou de l'autre "
           "exclus. Libye : pas de données d'exportation déclarées par le partenaire (exclue).")
