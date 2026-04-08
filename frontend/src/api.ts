const json = <T>(r: Response): Promise<T> => {
  if (!r.ok) throw new Error(`${r.status} ${r.statusText}`);
  return r.json() as Promise<T>;
};

export async function getSeasonConfig() {
  return json<{ nba_season_id: string; league_year_end: number }>(await fetch("/api/season-config"));
}

export async function getMlMetrics() {
  return json<{
    available: boolean;
    metrics?: Record<string, unknown>;
    detail?: string;
  }>(await fetch("/api/ml-metrics"));
}

export async function getBrackets() {
  return json<{
    brackets: Array<{
      id: string;
      short_label: string;
      multiplier: number;
      cushion_mm: number;
      explanation: string;
    }>;
  }>(await fetch("/api/cba-brackets"));
}

export async function getPicks(leagueYear: number) {
  return json<{ picks: Array<{ id: string; label: string; trade_value: number }> }>(
    await fetch(`/api/picks?league_year=${leagueYear}`)
  );
}

export async function analyzeTrade(body: object) {
  const r = await fetch("/api/analyze", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(body),
  });
  if (!r.ok) {
    const t = await r.text();
    throw new Error(t || r.statusText);
  }
  return r.json() as Promise<AnalysisResult>;
}

export async function reloadPool() {
  return json<{ ok: boolean }>(await fetch("/api/reload-pool", { method: "POST" }));
}

export async function getTeams() {
  return json<{ teams: string[] }>(await fetch("/api/teams"));
}

export type RosterPlayer = {
  player_name: string;
  team: string;
  trade_value_score: number;
  talent_score: number;
  contract_value_score: number;
  salary_mm: number;
  player_id?: number;
  /** Offline ML 0–100 (VORP regression); optional */
  ml_value_score?: number;
  ml_vorp_predicted?: number;
  trade_value_hybrid?: number;
};

/** Full roster for one franchise (sorted by name); pass CSV team code (e.g. PHO, BRK). */
export async function getTeamRoster(team: string) {
  const qs = new URLSearchParams({ team, roster: "true" });
  return json<{ players: RosterPlayer[] }>(await fetch(`/api/players?${qs}`));
}

/** Loosely typed API response */
export type AnalysisResult = {
  team_a_label: string;
  team_b_label: string;
  profiles: Array<Record<string, unknown>>;
  salary: Record<string, unknown>;
  trade_value: Record<string, unknown>;
  charts: {
    bar: {
      labels: string[];
      colors: string[];
      metrics: Record<string, Array<number | null>>;
    };
    radar: { labels: string[]; series: RadarSeries[] };
  };
  verdict: Record<string, unknown>;
  verdict_ml?: Record<string, unknown> | null;
  balance_suggestions?: Array<{ category: string; title: string; detail: string }>;
  meta?: Record<string, unknown>;
};

export type RadarSeries = {
  label: string;
  data: number[];
  color: string;
  side?: string;
  dashed?: boolean;
};
