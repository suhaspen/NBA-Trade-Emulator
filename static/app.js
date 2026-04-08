let barChart;
let radarChart;
let lastAnalysis = null;

function el(id) {
  return document.getElementById(id);
}

function chartTheme() {
  const s = getComputedStyle(document.documentElement);
  const t = (k) => s.getPropertyValue(k).trim();
  return {
    tick: t("--chart-tick"),
    grid: t("--chart-grid"),
    legend: t("--chart-legend"),
  };
}

async function initSeasonDefaults() {
  try {
    const res = await fetch("/api/season-config");
    const d = await res.json();
    if (d.league_year_end != null) el("leagueYear").value = d.league_year_end;
  } catch (_) {
    /* keep HTML fallback */
  }
}

async function loadBrackets() {
  const res = await fetch("/api/cba-brackets");
  const data = await res.json();
  const brackets = data.brackets || [];
  for (const [selId, defaultId] of [["bracketA", "below_first_apron"], ["bracketB", "below_first_apron"]]) {
    const s = el(selId);
    s.innerHTML = "";
    for (const b of brackets) {
      const o = document.createElement("option");
      o.value = b.id;
      o.textContent = `${b.short_label} (~${b.multiplier}× + $${b.cushion_mm}M)`;
      if (b.id === defaultId) o.selected = true;
      s.appendChild(o);
    }
  }
}

async function loadPicks() {
  const y = parseInt(el("leagueYear").value, 10) || 2025;
  const res = await fetch(`/api/picks?league_year=${y}`);
  const data = await res.json();
  const opts = data.picks || [];
  for (const selId of ["picksA", "picksB"]) {
    const s = el(selId);
    s.innerHTML = "";
    for (const p of opts) {
      const o = document.createElement("option");
      o.value = p.id;
      o.textContent = `${p.label} (TV ${p.trade_value})`;
      s.appendChild(o);
    }
  }
}

function selectedValues(select) {
  return Array.from(select.selectedOptions).map((o) => o.value);
}

/** Supports: "Name", "Name|TEAM", "id:12345" */
function parsePlayerLine(line) {
  const t = line.trim();
  if (!t) return null;
  const idm = t.match(/^id:\s*(\d+)\s*$/i);
  if (idm) return { query: "", team: null, player_id: parseInt(idm[1], 10), match_salary_mm: null };
  const pipe = t.split("|").map((s) => s.trim());
  if (pipe.length === 2) {
    return { query: pipe[0], team: pipe[1] || null, player_id: null, match_salary_mm: null };
  }
  return { query: t, team: null, player_id: null, match_salary_mm: null };
}

function linesToPlayers(text) {
  return text
    .split("\n")
    .map(parsePlayerLine)
    .filter(Boolean);
}

async function runAnalysis() {
  const status = el("status");
  status.textContent = "Running…";
  const ly = parseInt(el("leagueYear").value, 10) || 2025;
  const body = {
    league_year: ly,
    team_a: {
      label: el("labelA").value || "Team A",
      salary_bracket: el("bracketA").value,
      players: linesToPlayers(el("playersA").value),
      picks: selectedValues(el("picksA")),
    },
    team_b: {
      label: el("labelB").value || "Team B",
      salary_bracket: el("bracketB").value,
      players: linesToPlayers(el("playersB").value),
      picks: selectedValues(el("picksB")),
    },
  };
  const res = await fetch("/api/analyze", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(body),
  });
  if (!res.ok) {
    const t = await res.text();
    status.textContent = `Error ${res.status}: ${t}`;
    return;
  }
  status.textContent = "";
  const out = await res.json();
  lastAnalysis = out;
  render(out);
}

function renderBalanceSuggestions(items) {
  const ul = el("balanceList");
  ul.innerHTML = "";
  const list = items || [];
  if (list.length === 0) {
    const li = document.createElement("li");
    li.innerHTML = "<p class=\"sug-detail\">No extra notes.</p>";
    ul.appendChild(li);
    return;
  }
  for (const s of list) {
    const li = document.createElement("li");
    const cat = s.category || "note";
    li.innerHTML = `
      <div class="sug-cat">${cat}</div>
      <div class="sug-title">${escapeHtml(s.title || "")}</div>
      <p class="sug-detail">${escapeHtml(s.detail || "")}</p>
    `;
    ul.appendChild(li);
  }
}

function escapeHtml(text) {
  const d = document.createElement("div");
  d.textContent = text;
  return d.innerHTML;
}

function render(data) {
  el("results").classList.remove("hidden");
  const sal = data.salary;
  const la = data.team_a_label;
  const lb = data.team_b_label;
  const theme = chartTheme();

  const sb = el("salaryBlock");
  sb.innerHTML = `
    <div class="kv"><strong>${escapeHtml(la)} band</strong>${escapeHtml(sal.team_a_band)} (${sal.team_a_multiplier}× + $${sal.team_a_cushion_mm}M)</div>
    <div class="kv"><strong>${escapeHtml(lb)} band</strong>${escapeHtml(sal.team_b_band)} (${sal.team_b_multiplier}× + $${sal.team_b_cushion_mm}M)</div>
    <div class="kv"><strong>${escapeHtml(la)} outgoing (match)</strong>$${sal.team_a_outgoing_mm}M</div>
    <div class="kv"><strong>${escapeHtml(la)} incoming</strong>$${sal.team_a_incoming_mm}M</div>
    <div class="kv"><strong>${escapeHtml(la)} max send</strong>$${sal.team_a_max_outgoing_mm}M</div>
    <div class="kv"><strong>${escapeHtml(lb)} outgoing (match)</strong>$${sal.team_b_outgoing_mm}M</div>
    <div class="kv"><strong>${escapeHtml(lb)} incoming</strong>$${sal.team_b_incoming_mm}M</div>
    <div class="kv"><strong>${escapeHtml(lb)} max send</strong>$${sal.team_b_max_outgoing_mm}M</div>
  `;

  const sv = el("salaryVerdict");
  if (sal.trade_legal) {
    sv.textContent = sal.disclaimer || "Preset bands satisfied for both sides.";
    sv.dataset.tone = "success";
  } else {
    sv.textContent = sal.disclaimer || "At least one side fails its selected band.";
    sv.dataset.tone = "danger";
  }

  const tv = data.trade_value;
  const meta = data.meta || {};
  el("tvBlock").innerHTML = `
    <div class="kv"><strong>${escapeHtml(la)} total TV</strong>${tv.team_a_total} <span style="color:var(--text-secondary);font-size:0.85em">(pl ${tv.team_a_from_players} + pk ${tv.team_a_from_picks})</span></div>
    <div class="kv"><strong>${escapeHtml(lb)} total TV</strong>${tv.team_b_total} <span style="color:var(--text-secondary);font-size:0.85em">(pl ${tv.team_b_from_players} + pk ${tv.team_b_from_picks})</span></div>
    <div class="kv"><strong>Surplus (A − B)</strong>${tv.surplus_for_team_a}</div>
    <div class="kv"><strong>Score blend</strong>${escapeHtml(meta.trade_value_blend || "—")}</div>
  `;

  renderBalanceSuggestions(data.balance_suggestions);

  const tbody = el("profileTable").querySelector("tbody");
  tbody.innerHTML = "";
  for (const p of data.profiles) {
    const tr = document.createElement("tr");
    if (p.asset_type === "pick") tr.classList.add("pick-row");
    const matchSal = p.aggregation_salary_mm != null ? p.aggregation_salary_mm.toFixed(2) : "—";
    const cells = [
      p.side,
      p.player_name,
      p.team ?? "",
      p.age != null ? p.age.toFixed(1) : "—",
      p.salary_mm != null ? p.salary_mm.toFixed(2) : "—",
      p.contract_years_remaining != null ? p.contract_years_remaining : "—",
      p.trade_value_score != null ? p.trade_value_score.toFixed(1) : "—",
      p.talent_score != null ? p.talent_score.toFixed(1) : "—",
      p.contract_value_score != null ? p.contract_value_score.toFixed(1) : "—",
      matchSal,
      p.pts != null ? p.pts.toFixed(1) : "—",
      p.ast != null ? p.ast.toFixed(1) : "—",
      p.reb != null ? p.reb.toFixed(1) : "—",
      p.bpm != null ? p.bpm.toFixed(1) : "—",
      p.vorp != null ? p.vorp.toFixed(2) : "—",
    ];
    for (const c of cells) {
      const td = document.createElement("td");
      td.textContent = c;
      tr.appendChild(td);
    }
    tbody.appendChild(tr);
  }

  const bc = data.charts.bar;
  const metrics = Object.keys(bc.metrics);
  const datasets = bc.labels.map((label, i) => {
    const color = bc.colors[i];
    return {
      label,
      backgroundColor: color,
      borderColor: color,
      data: metrics.map((m) => {
        const v = bc.metrics[m][i];
        return v == null ? 0 : v;
      }),
    };
  });

  const barCtx = el("barChart").getContext("2d");
  if (barChart) barChart.destroy();
  barChart = new Chart(barCtx, {
    type: "bar",
    data: {
      labels: metrics,
      datasets,
    },
    options: {
      responsive: true,
      maintainAspectRatio: false,
      plugins: {
        legend: { labels: { color: theme.legend } },
      },
      scales: {
        x: {
          ticks: { color: theme.tick, maxRotation: 40, minRotation: 0 },
          grid: { color: theme.grid },
        },
        y: {
          ticks: { color: theme.tick },
          grid: { color: theme.grid },
          beginAtZero: true,
        },
      },
    },
  });

  const rd = data.charts.radar;
  const radarCtx = el("radarChart").getContext("2d");
  if (radarChart) radarChart.destroy();
  radarChart = new Chart(radarCtx, {
    type: "radar",
    data: {
      labels: rd.labels,
      datasets: rd.series.map((s) => ({
        label: s.label,
        data: s.data,
        borderColor: s.color,
        backgroundColor: hexToRgba(s.color, s.dashed ? 0.06 : 0.14),
        borderWidth: 2,
        borderDash: s.dashed ? [6, 4] : [],
        pointBackgroundColor: s.color,
      })),
    },
    options: {
      responsive: true,
      maintainAspectRatio: false,
      scales: {
        r: {
          angleLines: { color: theme.grid },
          grid: { color: theme.grid },
          suggestedMin: 0,
          suggestedMax: 100,
          ticks: { color: theme.tick, backdropColor: "transparent" },
          pointLabels: { color: theme.legend, font: { size: 11 } },
        },
      },
      plugins: {
        legend: {
          labels: { color: theme.legend },
        },
      },
    },
  });

  const v = data.verdict;
  el("verdictText").textContent = `Value lean: ${v.verdict_team}. ${v.salary_cap_note}`;
  el("verdictReason").textContent = v.reason;
}

function hexToRgba(hex, a) {
  const h = hex.replace("#", "");
  const full = h.length === 3 ? h.split("").map((c) => c + c).join("") : h;
  const bigint = parseInt(full, 16);
  const r = (bigint >> 16) & 255;
  const g = (bigint >> 8) & 255;
  const b = bigint & 255;
  return `rgba(${r},${g},${b},${a})`;
}

async function reloadPool() {
  const status = el("status");
  status.textContent = "Reloading CSV…";
  const res = await fetch("/api/reload-pool", { method: "POST" });
  if (!res.ok) {
    status.textContent = "Reload failed";
    return;
  }
  status.textContent = "Data cache cleared — next run loads fresh CSV.";
}

function downloadJson() {
  if (!lastAnalysis) {
    el("status").textContent = "Run analysis first.";
    return;
  }
  const blob = new Blob([JSON.stringify(lastAnalysis, null, 2)], { type: "application/json" });
  const a = document.createElement("a");
  a.href = URL.createObjectURL(blob);
  a.download = "trade_analysis.json";
  a.click();
  URL.revokeObjectURL(a.href);
}

el("runBtn").addEventListener("click", () => runAnalysis().catch((e) => {
  el("status").textContent = String(e);
}));
el("exportBtn").addEventListener("click", downloadJson);
el("reloadBtn").addEventListener("click", () => reloadPool().catch((e) => { el("status").textContent = String(e); }));
el("leagueYear").addEventListener("change", () => loadPicks().catch(() => {}));

initSeasonDefaults()
  .then(() => loadBrackets())
  .then(() => loadPicks())
  .catch((e) => {
    el("status").textContent = String(e);
  });
