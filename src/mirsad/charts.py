"""Chart styling shared by scripts (matplotlib PNG) and app (Plotly)."""
POLICY_LABELS = {
    "mirsad": "MIRSAD + exploration (ε=0,1)",
    "model_er": "MIRSAD — classement ER (ε=0)",
    "model_p": "Modèle P(fraude)",
    "rules": "Règles (profil importateur)",
    "random": "Aléatoire",
}
# reference categorical palette (fixed order), random = neutral baseline gray
POLICY_COLORS = {"mirsad": "#2a78d6", "model_er": "#eb6834", "model_p": "#1baf7a",
                 "rules": "#eda100", "random": "#8a8984"}
EPS_COLORS = {0.0: "#eb6834", 0.1: "#2a78d6", 0.2: "#1baf7a"}
INK, INK2, GRID = "#0b0b0b", "#52514e", "#e6e5e0"


def style_axes(ax):
    for s in ["top", "right"]:
        ax.spines[s].set_visible(False)
    for s in ["left", "bottom"]:
        ax.spines[s].set_color(GRID)
    ax.tick_params(colors=INK2, labelsize=9)
    ax.grid(axis="y", color=GRID, linewidth=0.8)
    ax.set_axisbelow(True)
