export type PlayerLine = {
  query: string;
  team: string | null;
  player_id: number | null;
  match_salary_mm: number | null;
};

/** Players chosen from roster multi-select (stable IDs from CSV). */
export function playerLinesFromIds(playerIds: number[]): PlayerLine[] {
  return playerIds.map((player_id) => ({
    query: "",
    team: null,
    player_id,
    match_salary_mm: null,
  }));
}

/** Roster selections first, then manual lines (name / id:… / Name|TEAM). */
export function mergeRosterAndManualLines(playerIds: number[], manualText: string): PlayerLine[] {
  return [...playerLinesFromIds(playerIds), ...parsePlayerLines(manualText)];
}

export function parsePlayerLines(text: string): PlayerLine[] {
  const out: PlayerLine[] = [];
  for (const raw of text.split("\n")) {
    const t = raw.trim();
    if (!t) continue;
    const idm = t.match(/^id:\s*(\d+)\s*$/i);
    if (idm) {
      out.push({ query: "", team: null, player_id: parseInt(idm[1]!, 10), match_salary_mm: null });
      continue;
    }
    const parts = t.split("|").map((s) => s.trim());
    if (parts.length === 2) {
      out.push({
        query: parts[0]!,
        team: parts[1] || null,
        player_id: null,
        match_salary_mm: null,
      });
    } else {
      out.push({ query: t, team: null, player_id: null, match_salary_mm: null });
    }
  }
  return out;
}
