
import pandas as pd
import numpy as np
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
import matplotlib.patches as mpatches
from matplotlib.patches import FancyBboxPatch
import math

# ─── Zerve Design System ───────────────────────────────────────────────────────
TC_BG       = "#1D1D20"
TC_TEXT     = "#fbfbff"
TC_MUTED    = "#909094"
TC_BLUE     = "#A1C9F4"
TC_ORANGE   = "#FFB482"
TC_GREEN    = "#8DE5A1"
TC_CORAL    = "#FF9F9B"
TC_LAVENDER = "#D0BBFF"
TC_YELLOW   = "#ffd400"
TC_PURPLE   = "#9467BD"
OKC_COLOR   = "#007AC1"   # OKC thunder blue
DEN_COLOR   = "#FEC524"   # Nuggets gold

plt.rcParams.update({
    "figure.facecolor": TC_BG, "axes.facecolor": TC_BG,
    "text.color": TC_TEXT, "axes.labelcolor": TC_TEXT,
    "xtick.color": TC_TEXT, "ytick.color": TC_TEXT,
    "axes.edgecolor": TC_MUTED, "grid.color": "#2e2e34",
    "font.family": "DejaVu Sans",
})

# ─── 1. Extract the three players ────────────────────────────────────────────
# trade_value_rankings has 16 cols; df has 49 cols including contract_years_remaining
# Merge to get full picture
_tvr = trade_value_rankings.copy()
_full = df[["player_name", "contract_years_remaining", "stl", "blk",
            "ws", "ts_pct", "obpm", "dbpm", "per", "fg_pct", "fg3_pct",
            "efg_pct", "ft_pct", "min_per_game", "games_played"]].copy()

trade_profiles = _tvr.merge(_full, on="player_name", how="left")

# Fuzzy match for special chars (Jokić, etc.)
def _find_player(df_in, name_fragment):
    mask = df_in["player_name"].str.contains(name_fragment, case=False, na=False, regex=False)
    rows = df_in[mask]
    if len(rows) == 0:
        raise ValueError(f"Player '{name_fragment}' not found in dataset!")
    return rows.iloc[0]

chet   = _find_player(trade_profiles, "Holmgren")
sga    = _find_player(trade_profiles, "Gilgeous")
jokic  = _find_player(trade_profiles, "Joki")

trade_players_df = pd.DataFrame([chet, sga, jokic]).reset_index(drop=True)
trade_players_df["side"] = ["OKC", "OKC", "DEN"]

print("=" * 80)
print("  🏀  OKC vs DEN TRADE ANALYSIS: CHET + SGA ⬌ JOKIĆ")
print("=" * 80)

# ─── 2. Individual Player Profiles ────────────────────────────────────────────
print("\n📊 INDIVIDUAL PLAYER PROFILES")
print("-" * 80)
_profile_cols = ["player_name", "team", "age", "salary_mm", "contract_years_remaining",
                 "trade_value_score", "pts", "ast", "reb", "bpm", "vorp",
                 "health_score", "contract_efficiency"]
_headers = ["Player", "Team", "Age", "Salary($M)", "Yrs Left", "TradeVal",
            "PTS", "AST", "REB", "BPM", "VORP", "Health", "ContractEff"]

pd.set_option("display.float_format", "{:.2f}".format)
print(trade_players_df[_profile_cols].to_string(index=False, header=_headers))

# ─── 3. Trade Value Balance & Salary Check ────────────────────────────────────
chet_tv  = float(chet["trade_value_score"])
sga_tv   = float(sga["trade_value_score"])
jokic_tv = float(jokic["trade_value_score"])

chet_sal  = float(chet["salary_mm"])
sga_sal   = float(sga["salary_mm"])
jokic_sal = float(jokic["salary_mm"])

okc_tv_total  = chet_tv + sga_tv
den_tv_total  = jokic_tv
tv_surplus    = okc_tv_total - den_tv_total   # positive = OKC giving more

okc_sal_total = chet_sal + sga_sal
den_sal_total = jokic_sal
sal_diff      = okc_sal_total - den_sal_total  # positive = OKC sending more $$

# NBA trade rules: outgoing salary ≤ incoming * 1.25 + $0.1M (simplified rule for teams NOT at apron)
# For teams at apron: incoming must match outgoing within 110%
# Simple check: each side's outgoing vs incoming
okc_outgoing = okc_sal_total
den_outgoing = den_sal_total

# OKC receives Jokic (den_outgoing), DEN receives OKC players (okc_outgoing)
okc_incoming = den_outgoing
den_incoming = okc_outgoing

okc_max_allowed = okc_incoming * 1.25 + 0.1   # OKC can send up to this
den_max_allowed = den_incoming * 1.25 + 0.1   # DEN can send up to this

# Can OKC send out okc_outgoing?
okc_salary_legal = okc_outgoing <= okc_max_allowed
# Can DEN send out den_outgoing?
den_salary_legal = den_outgoing <= den_max_allowed
trade_legal = okc_salary_legal and den_salary_legal

print(f"\n\n💰 SALARY MATCHING ANALYSIS (NBA Trade Rules: 125% + $100K)")
print("-" * 80)
print(f"  OKC Side  (Chet + SGA):  ${okc_sal_total:.1f}M outgoing | Receives: ${okc_incoming:.1f}M")
print(f"  DEN Side  (Jokić):        ${den_sal_total:.1f}M outgoing | Receives: ${den_incoming:.1f}M")
print(f"\n  OKC sends ${okc_outgoing:.1f}M — max allowed under 125% rule: ${okc_max_allowed:.1f}M → {'✅ LEGAL' if okc_salary_legal else '❌ ILLEGAL'}")
print(f"  DEN sends ${den_outgoing:.1f}M — max allowed under 125% rule: ${den_max_allowed:.1f}M → {'✅ LEGAL' if den_salary_legal else '❌ ILLEGAL'}")
print(f"\n  Trade Salary Legality: {'✅ TRADE IS SALARY-LEGAL' if trade_legal else '❌ TRADE IS NOT SALARY-LEGAL'}")
print(f"  Salary differential: ${abs(sal_diff):.1f}M ({'OKC sends more' if sal_diff > 0 else 'DEN sends more'})")

print(f"\n\n⚖️  TRADE VALUE BALANCE")
print("-" * 80)
print(f"  OKC Side (Chet + SGA):  TV = {okc_tv_total:.1f}  (Chet: {chet_tv:.1f} + SGA: {sga_tv:.1f})")
print(f"  DEN Side (Jokić):        TV = {den_tv_total:.1f}")
print(f"  Surplus/Deficit:          {'+' if tv_surplus > 0 else ''}{tv_surplus:.1f} ({'OKC giving MORE value' if tv_surplus > 0 else 'DEN giving MORE value'})")

# ─── 4. Grouped Bar Chart ─────────────────────────────────────────────────────
bar_metrics = {
    "Trade\nValue":  [chet_tv,              sga_tv,              jokic_tv],
    "Salary\n($M)":  [chet_sal,             sga_sal,             jokic_sal],
    "Age":           [float(chet["age"]),    float(sga["age"]),   float(jokic["age"])],
    "PTS":           [float(chet["pts"]),    float(sga["pts"]),   float(jokic["pts"])],
    "AST":           [float(chet["ast"]),    float(sga["ast"]),   float(jokic["ast"])],
    "REB":           [float(chet["reb"]),    float(sga["reb"]),   float(jokic["reb"])],
    "BPM":           [float(chet["bpm"]),    float(sga["bpm"]),   float(jokic["bpm"])],
}
metric_names = list(bar_metrics.keys())
n_metrics = len(metric_names)
players   = ["Chet Holmgren", "Shai G-A", "Nikola Jokić"]
p_colors  = [TC_BLUE, TC_ORANGE, DEN_COLOR]

trade_bar_chart_fig, axs = plt.subplots(1, n_metrics, figsize=(20, 7))
trade_bar_chart_fig.patch.set_facecolor(TC_BG)
trade_bar_chart_fig.suptitle("OKC (Chet + SGA)  ⬌  DEN (Jokić) — Trade Metric Breakdown",
                   fontsize=15, fontweight="bold", color=TC_TEXT, y=1.01)

for i, (metric, vals) in enumerate(bar_metrics.items()):
    ax = axs[i]
    ax.set_facecolor(TC_BG)
    _bars = ax.bar(players, vals, color=p_colors, width=0.6, edgecolor=TC_BG, linewidth=1.2)

    for bar_r, v in zip(_bars, vals):
        ax.text(bar_r.get_x() + bar_r.get_width()/2, bar_r.get_height() + max(vals)*0.02,
                f"{v:.1f}", ha="center", va="bottom", fontsize=9, color=TC_TEXT, fontweight="bold")

    ax.set_title(metric, color=TC_TEXT, fontsize=11, fontweight="bold", pad=8)
    ax.set_xticks([])
    ax.spines[["top","right","bottom"]].set_visible(False)
    ax.spines["left"].set_color(TC_MUTED)
    ax.tick_params(axis="y", labelsize=8, colors=TC_MUTED)
    ax.yaxis.grid(True, linestyle="--", alpha=0.3, color=TC_MUTED)
    ax.set_axisbelow(True)

    # Shade OKC vs DEN side
    if i == 0:
        ax.set_ylabel("Value", color=TC_MUTED, fontsize=8)

# Legend
_patches = [mpatches.Patch(color=c, label=p) for c, p in zip(p_colors, players)]
trade_bar_chart_fig.legend(handles=_patches, loc="lower center", ncol=3,
              framealpha=0, fontsize=10, labelcolor=TC_TEXT, bbox_to_anchor=(0.5, -0.06))
trade_bar_chart_fig.tight_layout()
print("\n\n[Chart 1 – Grouped Bar Chart: Trade Metric Breakdown — rendered]")

# ─── 5. Radar / Spider Chart ──────────────────────────────────────────────────
# 6 dimensions: scoring, playmaking, defense, efficiency, contract_value, longevity
# Normalize each to 0-100 relative to the full trade_value_rankings pool

def _norm100(val, series):
    lo, hi = series.min(), series.max()
    return 100 * (val - lo) / (hi - lo + 1e-9)

_tvr2 = trade_value_rankings.copy()
_tvr2 = _tvr2.merge(_full, on="player_name", how="left")

def _radar_dims(player_row, pool):
    # Scoring: pts
    scoring      = _norm100(player_row["pts"], pool["pts"])
    # Playmaking: ast + stl proxy (ast dominates)
    playmaking   = _norm100(player_row["ast"], pool["ast"])
    # Defense: dbpm mapped from trade_profiles
    _dbpm_vals   = _tvr2["dbpm"] if "dbpm" in _tvr2.columns else pool["bpm"] * 0
    _dbpm_row    = float(player_row.get("dbpm", 0)) if "dbpm" in player_row else 0.0
    defense      = _norm100(_dbpm_row, _tvr2["dbpm"])
    # Efficiency: ts_pct
    _ts_vals     = _tvr2["ts_pct"] if "ts_pct" in _tvr2.columns else pool["pts"] * 0
    _ts_row      = float(player_row.get("ts_pct", 0)) if "ts_pct" in player_row else 0.0
    efficiency   = _norm100(_ts_row, _tvr2["ts_pct"])
    # Contract Value: contract_efficiency
    contract_val = _norm100(player_row["contract_efficiency"], pool["contract_efficiency"])
    # Longevity (age curve): age_multiplier * health_score combined
    longevity_raw = float(player_row["age_multiplier"]) * float(player_row["health_score"])
    pool_long     = pool["age_multiplier"] * pool["health_score"]
    longevity     = _norm100(longevity_raw, pool_long)
    return [scoring, playmaking, defense, efficiency, contract_val, longevity]

radar_labels   = ["Scoring", "Playmaking", "Defense", "Efficiency", "Contract\nValue", "Longevity"]
chet_radar     = _radar_dims(chet,  _tvr)
sga_radar      = _radar_dims(sga,   _tvr)
jokic_radar    = _radar_dims(jokic, _tvr)

n_dims = len(radar_labels)
angles = np.linspace(0, 2 * np.pi, n_dims, endpoint=False).tolist()
angles += angles[:1]  # close the polygon

trade_radar_fig = plt.figure(figsize=(10, 9))
trade_radar_fig.patch.set_facecolor(TC_BG)
radar_ax = trade_radar_fig.add_subplot(111, polar=True)
radar_ax.set_facecolor(TC_BG)

for vals, color, player_name, lw in [
    (chet_radar,  TC_BLUE,   "Chet Holmgren",  2.5),
    (sga_radar,   TC_ORANGE, "Shai G-A",       2.5),
    (jokic_radar, DEN_COLOR, "Nikola Jokić",   2.5),
]:
    v_closed = vals + vals[:1]
    radar_ax.plot(angles, v_closed, color=color, linewidth=lw, linestyle="solid", label=player_name)
    radar_ax.fill(angles, v_closed, color=color, alpha=0.12)

# Gridlines and axis styling
radar_ax.set_xticks(angles[:-1])
radar_ax.set_xticklabels(radar_labels, size=11, color=TC_TEXT, fontweight="bold")
radar_ax.set_ylim(0, 100)
radar_ax.set_yticks([20, 40, 60, 80, 100])
radar_ax.set_yticklabels(["20", "40", "60", "80", "100"], size=7, color=TC_MUTED)
radar_ax.yaxis.grid(True,  linestyle="--", alpha=0.25, color=TC_MUTED)
radar_ax.xaxis.grid(True,  linestyle="-",  alpha=0.2,  color=TC_MUTED)
radar_ax.spines["polar"].set_color(TC_MUTED)
radar_ax.tick_params(pad=12)

radar_ax.set_title("Player Radar: 6 Trade Dimensions\nChet + SGA (OKC)  vs  Jokić (DEN)",
                   color=TC_TEXT, fontsize=13, fontweight="bold", pad=20)
radar_ax.legend(loc="lower left", bbox_to_anchor=(0.02, -0.12), framealpha=0,
                fontsize=11, labelcolor=TC_TEXT)
trade_radar_fig.tight_layout()
print("[Chart 2 – Radar Chart: 6-Dimension Player Comparison — rendered]")

# ─── 6. Trade Verdict ─────────────────────────────────────────────────────────
print("\n" + "=" * 80)
print("  🏆  TRADE VERDICT")
print("=" * 80)

winner = "OKC wins" if tv_surplus < 0 else ("DEN wins" if tv_surplus > 0 else "Even trade")
margin = abs(tv_surplus)

if tv_surplus < -5:
    verdict_team = "DEN"
    verdict_reason = (f"Jokić is the highest-valued player in the dataset (TV: {jokic_tv:.1f}/100). "
                      f"Even combining Chet ({chet_tv:.1f}) + SGA ({sga_tv:.1f}) = {okc_tv_total:.1f} "
                      f"still falls {margin:.1f} TV points short of Jokić's singular dominance.")
elif tv_surplus > 5:
    verdict_team = "OKC"
    verdict_reason = (f"OKC's combined package (TV: {okc_tv_total:.1f}) exceeds Jokić ({jokic_tv:.1f}) "
                      f"by {margin:.1f} TV points. Two prime-age cornerstones outvalue even the best player.")
else:
    verdict_team = "Roughly Even"
    verdict_reason = "Trade values are nearly balanced — this is a fair deal for both teams."

print(f"\n  Trade Value:  OKC ({okc_tv_total:.1f})  vs  DEN ({den_tv_total:.1f})")
print(f"  TV Surplus:   {'+' if tv_surplus >= 0 else ''}{tv_surplus:.1f} → {winner} (by {margin:.1f} pts)")
print(f"\n  💡 Verdict: {verdict_team}")
print(f"\n  📝 Reasoning:")
print(f"     {verdict_reason}")

print(f"\n  📅 Contract Considerations:")
chet_yrs  = int(chet.get("contract_years_remaining", 0))
sga_yrs   = int(sga.get("contract_years_remaining", 0))
jokic_yrs = int(jokic.get("contract_years_remaining", 0))
print(f"     Chet Holmgren: {chet_yrs} years remaining | Age {int(chet['age'])} → ascending trajectory")
print(f"     SGA:           {sga_yrs} years remaining | Age {int(sga['age'])} → peak prime window")
print(f"     Nikola Jokić:  {jokic_yrs} years remaining | Age {int(jokic['age'])} → still dominant but older")

print(f"\n  💵 Salary Cap:")
print(f"     {'✅ This trade is SALARY-LEGAL under NBA 125% matching rules.' if trade_legal else '❌ This trade is NOT salary-legal as structured. Additional players/picks needed.'}")
print(f"     OKC absorbs ${jokic_sal:.1f}M (Jokić) | DEN absorbs ${okc_sal_total:.1f}M (Chet + SGA)")
print(f"     Net cap change: DEN {'saves' if sal_diff > 0 else 'takes on'} ${abs(sal_diff):.1f}M vs current commitments")

print("\n" + "=" * 80)
print("  Charts rendered: [1] Grouped Bar Comparison  [2] Spider/Radar Chart")
print("=" * 80)
