import plotly.graph_objects as go
import streamlit as st

from common import fr, load_csv, load_json, load_parquet, page, pct
from mirsad.charts import EPS_COLORS, POLICY_COLORS, SERIES_COLORS, series_label

page("Simulation")
st.title("Simulation : ciblage sous budget, avec étiquettes sélectives")
st.markdown("Rejeu hebdomadaire de 50 semaines. Chaque semaine, le modèle n'apprend **que** des déclarations contrôlées "
            "par le passé, sélectionne k = r × N déclarations, puis seules celles-ci révèlent leur résultat. Dès la "
            "semaine 26, un **schéma de fraude simulé** apparaît : 25 nouveaux importateurs sous-évaluent 5 % des "
            "véhicules (chapitre 87). Aucun entraînement n'a lieu en direct ; tout est précalculé.")

s = load_csv("results/summary_by_seed.csv")
w = load_parquet("results/sim_runs.parquet")
m = load_json("results/metrics.json")
if s is None or w is None:
    st.error("Résultats de simulation absents : lancer `scripts/02_simulate.py`.")
    st.stop()

c1, c2 = st.columns(2)
r = c1.select_slider("Budget d'inspection r (part des déclarations contrôlées)", options=[0.02, 0.05, 0.10, 0.20],
                     value=0.05, format_func=lambda x: pct(x, 0))
eps = c2.select_slider("Exploration ε (part du budget consacrée à explorer)", options=[0.0, 0.1, 0.2], value=0.2,
                       format_func=lambda x: fr(x, 1))

g = s.groupby(["policy", "eps", "r"]).agg(["mean", "std"]).reset_index()


def series(pol, e, col):
    d = g[(g.policy == pol) & (g.eps == e)].sort_values("r")
    return d.r * 100, d[(col, "mean")] * 100, d[(col, "std")] * 100


a, b = st.columns(2)
with a:
    st.subheader("A · Revenu capturé selon le budget")
    col = st.radio("Mesure", ["revenue_at_k", "revenue_hist_at_k"], horizontal=True,
                   format_func=lambda x: {"revenue_at_k": "Toutes fraudes", "revenue_hist_at_k": "Fraudes historiques"}[x])
    fig = go.Figure()
    pols = [("random", 0.0), ("rules", 0.0), ("model_p", 0.0), ("mirsad", 0.0)] + ([("mirsad", eps)] if eps > 0 else [])
    for pol, e in pols:
        x, y, sd = series(pol, e, col)
        lab = series_label(pol, e)
        fig.add_trace(go.Scatter(x=x, y=y, error_y=dict(type="data", array=sd, thickness=1, width=3),
                                 name=lab, mode="lines+markers",
                                 line=dict(color=SERIES_COLORS[(pol, e)], width=3 if (pol, e) == ("mirsad", 0.0) else 2,
                                           dash="dash" if (pol == "mirsad" and e > 0) else "solid"),
                                 hovertemplate="r = %{x:.0f} %<br>%{y:.1f} % ± %{error_y.array:.1f}<extra>" + lab + "</extra>"))
    fig.update_layout(height=420, xaxis_title="Budget r (%)", yaxis_title="Revenu@k (% du revenu récupérable)",
                      legend=dict(orientation="h", y=-0.25), margin=dict(l=10, r=10, t=10, b=10),
                      plot_bgcolor="#fbfbfa", paper_bgcolor="#fbfbfa", hovermode="closest")
    fig.update_yaxes(gridcolor="#e6e5e0")
    fig.add_vline(x=r * 100, line_dash="dot", line_color="#999")
    st.plotly_chart(fig, width="stretch")
with b:
    st.subheader(f"B · Schéma injecté : revenu cumulé capturé (r = {pct(r, 0)})")
    W0 = m["drift"]["start_week"]
    ww = w[(w.r == r) & (w.week >= W0)].sort_values("week").copy()
    ww["cum"] = ww.groupby(["policy", "eps", "seed"]).rev_inj_sel.cumsum()
    tot = ww[(ww.policy == "random") & (ww.seed == 0)]
    fig = go.Figure()
    fig.add_trace(go.Scatter(x=tot.week, y=tot.rev_inj_total.cumsum() / 1e6, name="Total du schéma",
                             line=dict(color="#8a8984", dash="dash", width=1.5)))
    rb = ww[ww.policy == "rules"].groupby("week").cum.mean()
    fig.add_trace(go.Scatter(x=rb.index, y=rb.values / 1e6, name="Règles", line=dict(color=POLICY_COLORS["rules"], dash="dot")))
    for e in [0.0, 0.1, 0.2]:
        sub = ww[(ww.policy == "mirsad") & (ww.eps == e)]
        q = sub.groupby("week").cum.agg(["mean", "std"])
        fig.add_trace(go.Scatter(x=q.index, y=q["mean"] / 1e6, name=f"MIRSAD ε = {fr(e, 1)}",
                                 line=dict(color=EPS_COLORS[e], width=3 if e == eps else 1.5)))
    fig.update_layout(height=420, xaxis_title="Semaine", yaxis_title="M TND simulés (moyenne sur graines)",
                      legend=dict(orientation="h", y=-0.25), margin=dict(l=10, r=10, t=10, b=10),
                      plot_bgcolor="#fbfbfa", paper_bgcolor="#fbfbfa", hovermode="x unified")
    fig.update_yaxes(gridcolor="#e6e5e0")
    st.plotly_chart(fig, width="stretch")

st.subheader(f"Indicateurs à r = {pct(r, 0)} (moyenne ± écart-type, {len(m['seeds'])} graines)")
rows = []
for pol, e in [("random", 0.0), ("rules", 0.0), ("model_p", 0.0), ("mirsad", 0.0), ("mirsad", 0.1), ("mirsad", 0.2)]:
    d = g[(g.policy == pol) & (g.eps == e) & (g.r == r)]
    if not len(d):
        continue

    def v(c):
        return f"{pct(d[(c, 'mean')].iloc[0])} ± {fr(100 * d[(c, 'std')].iloc[0], 1)}"
    rows.append({"Politique": series_label(pol, e),
                 "Revenu@k": v("revenue_at_k"), "Revenu@k fraudes historiques": v("revenue_hist_at_k"),
                 "Précision@k": v("precision_at_k"), "Schéma injecté capturé": v("injected_recall_rev"),
                 "Faux-vert (revenu)": v("false_green_rev"),
                 "TND / contrôle": fr(d[("tnd_per_inspection", "mean")].iloc[0], 0)})
st.dataframe(rows, width="stretch", hide_index=True)


def gm(pol, e, c, stat="mean"):
    return float(g[(g.policy == pol) & (g.eps == e) & (g.r == r)][(c, stat)].iloc[0])


ratio = gm("mirsad", 0.0, "revenue_at_k") / gm("random", 0.0, "revenue_at_k")
stats = load_json("results/exploration_stats.json") or []
st_e = next((x for x in stats if abs(x["r"] - r) < 1e-9 and x["eps"] == (eps if eps > 0 else 0.2)
             and x["metric"] == "injected_recall_rev"), None)
expl = ""
if st_e:
    signif = "significative" if st_e["p_value_welch"] < 0.05 else "non significative"
    expl = (f"Exploration ε = {fr(st_e['eps'], 1)} contre ε = 0 sur le schéma injecté : écart moyen "
            f"{'+' if st_e['diff'] >= 0 else ''}{fr(100 * st_e['diff'], 1)} points (p = {fr(st_e['p_value_welch'], 3)}, "
            f"{signif}) ; pire graine {pct(st_e['min_seed_eps0'])} → {pct(st_e['min_seed_eps'])}. L'exploration est un "
            "<b>réglage de prudence</b> (moins de risque de rater un nouveau schéma), pas un gain moyen démontré.")
st.markdown(f"""<div class="caveat"><b>Lecture honnête (r = {pct(r, 0)}).</b> À budget égal, MIRSAD capture
{fr(ratio, 1)}× plus de revenu qu'une sélection aléatoire. Sur les fraudes historiques :
{pct(gm("mirsad", 0.0, "revenue_hist_at_k"))} contre {pct(gm("rules", 0.0, "revenue_hist_at_k"))} pour les règles par
profil importateur. Sur le schéma injecté, les règles restent très robustes et MIRSAD est <b>bimodal</b> : selon les
graines, il verrouille le schéma en quelques semaines ou le manque. {expl} Tout est mesuré sur données
synthétiques (10 graines, test de Welch).</div>""", unsafe_allow_html=True)
