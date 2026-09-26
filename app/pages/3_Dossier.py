import json

import streamlit as st

from common import fr, lane_html, load_json, page

page("Dossier")
st.title("Dossier d'enquête")
idx = load_json("results/dossiers/index.json")
if not idx:
    st.error("Aucun dossier : lancer `scripts/05_build_dossiers.py`.")
    st.stop()


def label(i):
    tag = " · ⚠ tentative d'injection" if i["demo_injection"] else ""
    return f"{i['case_id']} · {i['voie']} · {fr(i['montant_en_jeu_TND'], 0)} TND{tag}"


options = {label(i): i for i in idx}
first_inj = next((k for k, i in options.items() if i["demo_injection"]), None)
choice = st.selectbox("Cas rouge", list(options), index=0,
                      help=f"Le cas de démonstration d'injection est : {first_inj}")
meta = options[choice]
cid = meta["case_id"]
d = load_json(f"results/dossiers/{cid}.json")
trace = load_json(f"results/traces/{cid}.json") or []

mode = d.get("_mode")
last_errs = (d.get("_validation") or [{}])[-1].get("erreurs", [])
badges = {
    "llm_valide": ("#0f766e", f"Rédigé par LLM ({d.get('_modele')}) · validé"),
    "llm_valide_apres_correction": ("#0f766e", f"LLM ({d.get('_modele')}) · validé après 1 correction"),
    "fallback": ("#6b5b00", "Généré sans LLM (gabarit déterministe) · validé" if not last_errs else "Gabarit · ERREURS"),
}
col, txt = badges.get(mode, ("#777", mode))
st.markdown(f'{lane_html(d["voie"])} &nbsp; <span class="badge" style="color:{col};border-color:{col}">{txt}</span>'
            + (f'<span class="badge" style="color:#555;border-color:#aaa">{d.get("_raison_fallback")}</span>'
               if d.get("_raison_fallback") else ""), unsafe_allow_html=True)

c = st.columns(4)
c[0].metric("Montant en jeu", f"{fr(d['montant_en_jeu_TND'], 0)} TND")
c[1].metric("Probabilité de fraude", f"{fr(100 * d['probabilite_fraude'], 2 if d['probabilite_fraude'] > 0.99 else 1)} %")
c[2].metric("Confiance du dossier", d["niveau_confiance"])
c[3].metric("Étapes d'enquête", len(trace))

evid = {}
for s in trace:
    o = s.get("output", {})
    if isinstance(o, dict) and "evidence_id" in o:
        evid[o["evidence_id"]] = s["tool"]


def chips(ids):
    return " ".join(f'<span class="chip" title="{evid.get(i, "")}">{i}</span>' for i in ids)


st.subheader("Résumé")
st.write(d["resume"])

left, right = st.columns([3, 2])
with left:
    st.subheader("Faits établis")
    for f in d["faits"]:
        st.markdown(f"- {f['texte']} {chips(f['evidence_ids'])}", unsafe_allow_html=True)
    st.subheader("Hypothèses")
    for h in d["hypotheses"]:
        st.markdown(f"- **{h['type']}** : {h['justification']} {chips(h['evidence_ids'])}", unsafe_allow_html=True)
with right:
    st.subheader("Contrôles recommandés")
    for x in d["controles_recommandes"]:
        st.markdown(f"- {x}")
    st.subheader("Base légale")
    if d["base_legale"]:
        for b in d["base_legale"]:
            st.markdown(f"> {b['extrait']}  \n— *{b['source']}* {chips([b['chunk_id']])}", unsafe_allow_html=True)
    else:
        st.markdown("*À confirmer par l'agent : aucun texte juridique n'a été chargé dans le corpus. MIRSAD "
                    "n'invente jamais de référence légale.*")
    st.subheader("Incertitudes")
    for x in d["incertitudes"]:
        st.markdown(f"- {x}")

st.divider()
st.subheader("Décision de l'agent")
key = f"decision_{cid}"
b1, b2, b3 = st.columns([1, 1, 3])
if b1.button("✅ Fraude confirmée", key=f"f_{cid}"):
    st.session_state[key] = "Fraude confirmée"
if b2.button("☑️ Conforme", key=f"c_{cid}"):
    st.session_state[key] = "Conforme"
if key in st.session_state:
    b3.info(f"Décision enregistrée (session uniquement) : **{st.session_state[key]}**. En production, ce retour "
            "alimente les profils de risque et le réentraînement.")

with st.expander("🔗 Chaîne de preuves : appels d'outils de l'enquête", expanded=False):
    for s in trace:
        st.markdown(f"**{s['step']}. `{s['tool']}`** ({s.get('duree_ms', 0)} ms), arguments : `{json.dumps(s['args'], ensure_ascii=False)}`")
        st.json(s["output"], expanded=False)
with st.expander("🛡️ Validation"):
    st.write("Le validateur rejette tout dossier dont un identifiant de preuve, un nombre ou une citation ne se retrouve "
             "pas dans les sorties d'outils, ou dont la voie diffère du scoreur.")
    st.json(d.get("_validation"))
with st.expander("🎯 Vérité terrain (simulation uniquement)"):
    st.write(f"Étiquette réelle dans le jeu synthétique : **{'fraude' if meta['label_fraud_revele_apres'] else 'conforme'}** · "
             f"schéma : **{'injecté (simulé)' if meta['scheme'] == 'injected' else 'historique'}**. Cette information "
             "n'est jamais visible par le modèle ni par l'agent avant le contrôle.")
st.download_button("Télécharger le dossier (JSON)", json.dumps(d, ensure_ascii=False, indent=2),
                   file_name=f"dossier_{cid}.json", mime="application/json")
