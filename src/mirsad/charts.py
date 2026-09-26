"""Chart styling shared by scripts (matplotlib PNG) and app (Plotly)."""
POLICY_LABELS = {
    "mirsad": "MIRSAD (montant en jeu)",
    "model_p": "Variante : probabilité seule",
    "rules": "Règles (profil importateur)",
    "random": "Aléatoire",
}


def series_label(policy: str, eps: float = 0.0) -> str:
    if policy == "mirsad":
        return "MIRSAD (montant en jeu, ε = 0)" if eps == 0 else f"MIRSAD + exploration (ε = {eps:g})".replace(".", ",")
    return POLICY_LABELS[policy]


# reference categorical palette (fixed order); random = neutral baseline gray
SERIES_ORDER = [("random", 0.0), ("rules", 0.0), ("model_p", 0.0), ("mirsad", 0.0), ("mirsad", 0.1), ("mirsad", 0.2)]
SERIES_COLORS = {("mirsad", 0.0): "#2a78d6", ("mirsad", 0.2): "#eb6834", ("model_p", 0.0): "#1baf7a",
                 ("rules", 0.0): "#eda100", ("mirsad", 0.1): "#e87ba4", ("random", 0.0): "#8a8984"}
POLICY_COLORS = {"mirsad": "#2a78d6", "model_p": "#1baf7a", "rules": "#eda100", "random": "#8a8984"}
EPS_COLORS = {0.0: "#2a78d6", 0.1: "#e87ba4", 0.2: "#eb6834"}
INK, INK2, GRID = "#0b0b0b", "#52514e", "#e6e5e0"


def style_axes(ax):
    for s in ["top", "right"]:
        ax.spines[s].set_visible(False)
    for s in ["left", "bottom"]:
        ax.spines[s].set_color(GRID)
    ax.tick_params(colors=INK2, labelsize=9)
    ax.grid(axis="y", color=GRID, linewidth=0.8)
    ax.set_axisbelow(True)
