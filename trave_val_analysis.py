
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import matplotlib.patches as mpatches
import matplotlib.lines as mlines
import numpy as np
import pandas as pd
from scipy.stats import pearsonr
from scipy.signal import savgol_filter
import unicodedata, re

# ── Zerve Design System ────────────────────────────────────────────────────────
VIZ_BG      = "#1D1D20"
VIZ_TEXT    = "#fbfbff"
VIZ_MUTED   = "#909094"
VIZ_ACCENT  = "#A1C9F4"
VIZ_ORANGE  = "#FFB482"
VIZ_GREEN   = "#8DE5A1"
VIZ_CORAL   = "#FF9F9B"
VIZ_LAVENDER= "#D0BBFF"
VIZ_YELLOW  = "#ffd400"
VIZ_BLUE    = "#1F77B4"
VIZ_PURPLE  = "#9467BD"

plt.rcParams.update({
    "figure.facecolor": VIZ_BG,
    "axes.facecolor": VIZ_BG,
    "text.color": VIZ_TEXT,
    "axes.labelcolor": VIZ_MUTED,
    "xtick.color": VIZ_MUTED,
    "ytick.color": VIZ_MUTED,
})

# ── Derive position from raw_pg (BRef per-game table has 'Pos' column) ────────
def _norm(name):
    if not isinstance(name, str): return ""
    nfkd = unicodedata.normalize("NFKD", name)
    ascii_n = nfkd.encode("ascii", "ignore").decode("ascii")
    return re.sub(r"[^a-z ]", "", ascii_n.lower()).strip()

POS_MAP = {
    "PG": "PG", "SG": "SG", "SF": "SF", "PF": "PF", "C": "C",
    "PG-SG": "PG", "SG-PG": "SG", "SG-SF": "SG", "SF-SG": "SF",
    "SF-PF": "SF", "PF-SF": "PF", "PF-C": "PF", "C-PF": "C",
    "PG-SF": "PG", "SG-PF": "SG",
}
POS_COLORS = {
    "PG": VIZ_ACCENT,
    "SG": VIZ_LAVENDER,
    "SF": VIZ_GREEN,
    "PF": VIZ_ORANGE,
    "C":  VIZ_CORAL,
}

pos_lookup = raw_pg[["Player", "Pos"]].copy()
pos_lookup = pos_lookup[pos_lookup["Player"].astype(str) != "Player"].copy()
pos_lookup["pos_simple"] = pos_lookup["Pos"].map(POS_MAP).fillna("SF")
pos_lookup["name_key"] = pos_lookup["Player"].astype(str).apply(_norm)
pos_lookup = pos_lookup.drop_duplicates("name_key")[["name_key", "pos_simple"]]

viz_df = trade_value_rankings.copy()
viz_df["name_key"] = viz_df["player_name"].astype(str).apply(_norm)
viz_df = viz_df.merge(pos_lookup, on="name_key", how="left")
viz_df["pos_simple"] = viz_df["pos_simple"].fillna("SF")

print(f"viz_df shape: {viz_df.shape}")
print(f"Position distribution:\n{viz_df['pos_simple'].value_counts().to_string()}")


# ══════════════════════════════════════════════════════════════════════════════
# CHART 1 — Top 30 Bar Chart, colored by Position + team label
# ══════════════════════════════════════════════════════════════════════════════
top30_viz = viz_df.head(30).copy().iloc[::-1]  # reversed → best player on top

chart1_fig, chart1_ax = plt.subplots(figsize=(14, 13))
chart1_fig.patch.set_facecolor(VIZ_BG)
chart1_ax.set_facecolor(VIZ_BG)

c1_players  = top30_viz["player_name"].values
c1_scores   = top30_viz["trade_value_score"].values
c1_teams    = top30_viz["team"].values
c1_positions= top30_viz["pos_simple"].values
c1_colors   = [POS_COLORS.get(str(p), VIZ_ACCENT) for p in c1_positions]
c1_y        = np.arange(len(c1_players))

chart1_ax.barh(c1_y, c1_scores, color=c1_colors, height=0.74, zorder=3, alpha=0.92)

for idx_c1, (sc_c1, tm_c1) in enumerate(zip(c1_scores, c1_teams)):
    chart1_ax.text(sc_c1 + 0.8, idx_c1, f"{sc_c1:.1f}",
                   va="center", ha="left", color=VIZ_TEXT, fontsize=8.5, fontweight="bold")
    chart1_ax.text(-1.5, idx_c1, str(tm_c1),
                   va="center", ha="right", color=VIZ_MUTED, fontsize=7.5, fontstyle="italic")

chart1_ax.set_yticks(c1_y)
chart1_ax.set_yticklabels(c1_players, color=VIZ_TEXT, fontsize=9)
chart1_ax.set_xlabel("Trade Value Score (0–100)", color=VIZ_MUTED, fontsize=11)
chart1_ax.set_title("🏀 NBA Trade Value Rankings — Top 30 Players (2023-24)",
                    color=VIZ_TEXT, fontsize=15, fontweight="bold", pad=16)
chart1_ax.set_xlim(-8, float(c1_scores.max()) + 14)
chart1_ax.tick_params(colors=VIZ_MUTED)
for sp_c1 in chart1_ax.spines.values(): sp_c1.set_visible(False)
chart1_ax.xaxis.grid(True, color="#333338", linewidth=0.5, zorder=0)

c1_legend = [mpatches.Patch(color=v, label=k) for k, v in POS_COLORS.items()]
chart1_ax.legend(handles=c1_legend, title="Position", title_fontsize=9,
                 loc="lower right", facecolor=VIZ_BG, edgecolor="#444448",
                 labelcolor=VIZ_TEXT, fontsize=9)

plt.tight_layout()
plt.savefig("top30_trade_value.png", dpi=130, bbox_inches="tight", facecolor=VIZ_BG)
plt.show()
print("✅ Chart 1: Top 30 Trade Value Rankings saved")


# ══════════════════════════════════════════════════════════════════════════════
# CHART 2 — Salary vs Trade Value — Quadrant Analysis
# ══════════════════════════════════════════════════════════════════════════════
scatter_df = viz_df[viz_df["salary_mm"] > 0].copy()
med_sal    = float(scatter_df["salary_mm"].median())
med_tv     = float(scatter_df["trade_value_score"].median())

chart2_fig, chart2_ax = plt.subplots(figsize=(14, 9))
chart2_fig.patch.set_facecolor(VIZ_BG)
chart2_ax.set_facecolor(VIZ_BG)

c2_colors = [POS_COLORS.get(str(p), VIZ_ACCENT) for p in scatter_df["pos_simple"]]
chart2_ax.scatter(scatter_df["salary_mm"], scatter_df["trade_value_score"],
                  c=c2_colors, s=65, alpha=0.82, zorder=3,
                  edgecolors="#2a2a2d", linewidths=0.4)

# Quadrant dividers
chart2_ax.axvline(med_sal, color="#555558", linewidth=1.2, linestyle="--", zorder=2, alpha=0.7)
chart2_ax.axhline(med_tv,  color="#555558", linewidth=1.2, linestyle="--", zorder=2, alpha=0.7)

x_min_c2 = float(scatter_df["salary_mm"].min()) - 2.0
x_max_c2 = float(scatter_df["salary_mm"].max()) + 5.0
y_min_c2 = float(scatter_df["trade_value_score"].min()) - 3.0
y_max_c2 = float(scatter_df["trade_value_score"].max()) + 5.0

# Quadrant shading
chart2_ax.fill_betweenx([med_tv, y_max_c2], x_min_c2, med_sal, color=VIZ_GREEN, alpha=0.05)
chart2_ax.fill_betweenx([med_tv, y_max_c2], med_sal, x_max_c2, color=VIZ_YELLOW, alpha=0.04)
chart2_ax.fill_betweenx([y_min_c2, med_tv], x_min_c2, med_sal, color=VIZ_MUTED, alpha=0.04)
chart2_ax.fill_betweenx([y_min_c2, med_tv], med_sal, x_max_c2, color=VIZ_CORAL, alpha=0.06)

# Quadrant labels
quad_fs = dict(fontsize=11, fontweight="bold", alpha=0.65, zorder=4)
chart2_ax.text(x_min_c2 + 0.5, y_max_c2 - 4.0, "💎 UNDERVALUED", color=VIZ_GREEN, **quad_fs)
chart2_ax.text(med_sal + 0.5,   y_max_c2 - 4.0, "⭐ ELITE / FAIR", color=VIZ_YELLOW, **quad_fs)
chart2_ax.text(x_min_c2 + 0.5, y_min_c2 + 1.5, "📉 CHEAP / LOW",  color=VIZ_MUTED,  **quad_fs)
chart2_ax.text(med_sal + 0.5,   y_min_c2 + 1.5, "🔥 OVERPAID",     color=VIZ_CORAL,  **quad_fs)

# Annotate top 20 players
for _, ann_row in viz_df[viz_df["salary_mm"] > 0].head(20).iterrows():
    chart2_ax.annotate(
        ann_row["player_name"].split()[-1],
        (float(ann_row["salary_mm"]), float(ann_row["trade_value_score"])),
        textcoords="offset points", xytext=(5, 3),
        color=VIZ_TEXT, fontsize=7.5, fontweight="500", zorder=5,
    )

# Pearson r
r_val_c2, _ = pearsonr(scatter_df["salary_mm"], scatter_df["trade_value_score"])
chart2_ax.text(0.98, 0.02, f"Pearson r = {r_val_c2:.2f}",
               transform=chart2_ax.transAxes, ha="right", va="bottom",
               color=VIZ_MUTED, fontsize=9)

chart2_ax.set_xlabel("Estimated Salary ($M, 2023-24)", color=VIZ_MUTED, fontsize=11)
chart2_ax.set_ylabel("Trade Value Score (0–100)", color=VIZ_MUTED, fontsize=11)
chart2_ax.set_title("Trade Value vs Salary — Identifying Market Inefficiencies",
                    color=VIZ_TEXT, fontsize=14, fontweight="bold", pad=14)
chart2_ax.tick_params(colors=VIZ_MUTED)
for sp_c2 in chart2_ax.spines.values(): sp_c2.set_color("#333338")
chart2_ax.xaxis.grid(True, color="#2a2a2d", linewidth=0.5, zorder=0)
chart2_ax.yaxis.grid(True, color="#2a2a2d", linewidth=0.5, zorder=0)
chart2_ax.set_xlim(x_min_c2, x_max_c2)
chart2_ax.set_ylim(y_min_c2, y_max_c2)

c2_legend = [mpatches.Patch(color=v, label=k) for k, v in POS_COLORS.items()]
chart2_ax.legend(handles=c2_legend, title="Position", title_fontsize=9,
                 loc="upper left", facecolor=VIZ_BG, edgecolor="#444448",
                 labelcolor=VIZ_TEXT, fontsize=9)

plt.tight_layout()
plt.savefig("trade_value_vs_salary.png", dpi=130, bbox_inches="tight", facecolor=VIZ_BG)
plt.show()
print("✅ Chart 2: Salary vs Trade Value scatter saved")


# ══════════════════════════════════════════════════════════════════════════════
# CHART 3 — Age vs Trade Value Curve
# ══════════════════════════════════════════════════════════════════════════════
age_df = viz_df.dropna(subset=["age", "trade_value_score"]).copy()
age_df["age_int"] = age_df["age"].astype(int)

chart3_fig, chart3_ax = plt.subplots(figsize=(13, 8))
chart3_fig.patch.set_facecolor(VIZ_BG)
chart3_ax.set_facecolor(VIZ_BG)

c3_colors = [POS_COLORS.get(str(p), VIZ_ACCENT) for p in age_df["pos_simple"]]
chart3_ax.scatter(age_df["age"], age_df["trade_value_score"],
                  c=c3_colors, s=55, alpha=0.70, zorder=3,
                  edgecolors="#2a2a2d", linewidths=0.3)

# Smoothed trendline
age_means = age_df.groupby("age_int")["trade_value_score"].mean().reset_index()
age_means = age_means.sort_values("age_int").reset_index(drop=True)
n_ages = len(age_means)
if n_ages >= 5:
    wl = min(7, n_ages if n_ages % 2 == 1 else n_ages - 1)
    smoothed = savgol_filter(age_means["trade_value_score"].values, window_length=wl, polyorder=2)
else:
    smoothed = age_means["trade_value_score"].values

chart3_ax.plot(age_means["age_int"].values, smoothed,
               color=VIZ_YELLOW, linewidth=2.8, zorder=4, label="Mean trend")

# Peak age
peak_idx = int(np.argmax(smoothed))
peak_age_val = int(age_means.loc[peak_idx, "age_int"])
peak_tv_val  = float(smoothed[peak_idx])
chart3_ax.annotate(f"Peak: Age {peak_age_val}",
                   xy=(peak_age_val, peak_tv_val),
                   xytext=(peak_age_val + 1.5, peak_tv_val + 3.5),
                   arrowprops=dict(arrowstyle="->", color=VIZ_YELLOW, lw=1.5),
                   color=VIZ_YELLOW, fontsize=10, fontweight="bold", zorder=5)

# Age band shading (Rookie / Rising / Prime / Veteran / Late)
age_bands = [
    (17.5, 22.5, "Rookie"),
    (22.5, 27.5, "Rising"),
    (27.5, 31.5, "Prime"),
    (31.5, 35.5, "Veteran"),
    (35.5, 43.5, "Late"),
]
band_colors_list = [VIZ_ACCENT, VIZ_GREEN, VIZ_YELLOW, VIZ_ORANGE, VIZ_CORAL]
for (ab_start, ab_end, ab_label), ab_color in zip(age_bands, band_colors_list):
    chart3_ax.axvspan(ab_start, ab_end, alpha=0.04, color=ab_color, zorder=0)
    chart3_ax.text((ab_start + ab_end) / 2, -2.5, ab_label,
                   ha="center", va="top", color=VIZ_MUTED, fontsize=7.5, alpha=0.7)

# Annotate top 10 players
for _, ann_row_c3 in viz_df.head(10).iterrows():
    if pd.notna(ann_row_c3["age"]):
        chart3_ax.annotate(
            ann_row_c3["player_name"].split()[-1],
            (float(ann_row_c3["age"]), float(ann_row_c3["trade_value_score"])),
            textcoords="offset points", xytext=(5, 3),
            color=VIZ_TEXT, fontsize=7.5, zorder=5,
        )

chart3_ax.set_xlabel("Age (years)", color=VIZ_MUTED, fontsize=11)
chart3_ax.set_ylabel("Trade Value Score (0–100)", color=VIZ_MUTED, fontsize=11)
chart3_ax.set_title("Age vs Trade Value — The NBA Player Career Arc",
                    color=VIZ_TEXT, fontsize=14, fontweight="bold", pad=14)
chart3_ax.tick_params(colors=VIZ_MUTED)
for sp_c3 in chart3_ax.spines.values(): sp_c3.set_color("#333338")
chart3_ax.xaxis.grid(True, color="#2a2a2d", linewidth=0.5, zorder=0)
chart3_ax.yaxis.grid(True, color="#2a2a2d", linewidth=0.5, zorder=0)

c3_legend = [mpatches.Patch(color=v, label=k) for k, v in POS_COLORS.items()]
trend_line_c3 = mlines.Line2D([], [], color=VIZ_YELLOW, linewidth=2.5, label="Mean trend")
chart3_ax.legend(handles=c3_legend + [trend_line_c3], title="Position",
                 title_fontsize=9, loc="upper right", facecolor=VIZ_BG,
                 edgecolor="#444448", labelcolor=VIZ_TEXT, fontsize=9)

plt.tight_layout()
plt.savefig("age_vs_trade_value.png", dpi=130, bbox_inches="tight", facecolor=VIZ_BG)
plt.show()
print("✅ Chart 3: Age vs Trade Value curve saved")


# ══════════════════════════════════════════════════════════════════════════════
# CHART 4 — Feature Importance (full model, color gradient)
# ══════════════════════════════════════════════════════════════════════════════
fi_df = importance_df.copy()
fi_df["pct"] = 100.0 * fi_df["importance"] / fi_df["importance"].sum()
fi_df = fi_df.sort_values("pct", ascending=True).reset_index(drop=True)
fi_labels = fi_df["feature"].str.replace("_", " ").str.title().values
fi_pcts   = fi_df["pct"].values
fi_max    = float(fi_pcts.max())

def _fi_color(pct_val):
    ratio = pct_val / fi_max
    if ratio >= 0.60:  return VIZ_YELLOW
    elif ratio >= 0.30: return VIZ_ACCENT
    elif ratio >= 0.15: return VIZ_GREEN
    else:               return VIZ_MUTED

fi_bar_colors = [_fi_color(p) for p in fi_pcts]

chart4_fig, chart4_ax = plt.subplots(figsize=(11, 8))
chart4_fig.patch.set_facecolor(VIZ_BG)
chart4_ax.set_facecolor(VIZ_BG)

c4_y = np.arange(len(fi_labels))
chart4_ax.barh(c4_y, fi_pcts, color=fi_bar_colors, height=0.68, zorder=3)

for idx_c4, pv_c4 in enumerate(fi_pcts):
    chart4_ax.text(float(pv_c4) + 0.2, idx_c4, f"{pv_c4:.1f}%",
                   va="center", ha="left", color=VIZ_TEXT, fontsize=8.5, fontweight="bold")

chart4_ax.set_yticks(c4_y)
chart4_ax.set_yticklabels(fi_labels, color=VIZ_TEXT, fontsize=10)
chart4_ax.set_xlabel("Feature Importance (%)", color=VIZ_MUTED, fontsize=11)
chart4_ax.set_title(f"Feature Importance — Trade Value Model ({model_name})",
                    color=VIZ_TEXT, fontsize=14, fontweight="bold", pad=14)
chart4_ax.tick_params(colors=VIZ_MUTED)
chart4_ax.set_xlim(0, fi_max + 10.0)
for sp_c4 in chart4_ax.spines.values(): sp_c4.set_visible(False)
chart4_ax.xaxis.grid(True, color="#333338", linewidth=0.5, zorder=0)

fi_legend = [
    mpatches.Patch(color=VIZ_YELLOW, label="High (>60% of max)"),
    mpatches.Patch(color=VIZ_ACCENT,  label="Medium (30–60%)"),
    mpatches.Patch(color=VIZ_GREEN,   label="Low (15–30%)"),
    mpatches.Patch(color=VIZ_MUTED,   label="Minor (<15%)"),
]
chart4_ax.legend(handles=fi_legend, loc="lower right", facecolor=VIZ_BG,
                 edgecolor="#444448", labelcolor=VIZ_TEXT, fontsize=9)

plt.tight_layout()
plt.savefig("feature_importance.png", dpi=130, bbox_inches="tight", facecolor=VIZ_BG)
plt.show()
print("✅ Chart 4: Feature Importance saved")

print("\n✅ All 4 charts rendered successfully.")
print(f"Model: {model_name} | Mean CV R²: {cv_scores.mean():.3f}")
print(f"\nTop 5 trade value players:")
print(viz_df[["player_name", "team", "pos_simple", "trade_value_score", "salary_mm", "age"]].head(5).to_string(index=False))
