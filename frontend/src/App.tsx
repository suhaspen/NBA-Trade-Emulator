import { useCallback, useEffect, useMemo, useState } from "react";
import {
  analyzeTrade,
  getBrackets,
  getMlMetrics,
  getPicks,
  getSeasonConfig,
  getTeamRoster,
  getTeams,
  reloadPool,
  type AnalysisResult,
  type RosterPlayer,
} from "./api";
import { mergeRosterAndManualLines } from "./playerLines";
import { ResultsView } from "./ResultsView";
import { teamOptionLabel } from "./teamMeta";

export default function App() {
  const [leagueYear, setLeagueYear] = useState(2025);
  const [brackets, setBrackets] = useState<
    Array<{ id: string; short_label: string; multiplier: number; cushion_mm: number }>
  >([]);
  const [pickOptions, setPickOptions] = useState<{ id: string; label: string; trade_value: number }[]>([]);
  const [teams, setTeams] = useState<string[]>([]);
  const [teamsLoading, setTeamsLoading] = useState(true);

  const [labelA, setLabelA] = useState("OKC");
  const [labelB, setLabelB] = useState("DEN");
  const [bracketA, setBracketA] = useState("below_first_apron");
  const [bracketB, setBracketB] = useState("below_first_apron");

  const [rosterA, setRosterA] = useState<RosterPlayer[]>([]);
  const [rosterB, setRosterB] = useState<RosterPlayer[]>([]);
  const [rosterLoadingA, setRosterLoadingA] = useState(false);
  const [rosterLoadingB, setRosterLoadingB] = useState(false);
  const [rosterSelA, setRosterSelA] = useState<number[]>([]);
  const [rosterSelB, setRosterSelB] = useState<number[]>([]);
  const [manualA, setManualA] = useState("");
  const [manualB, setManualB] = useState("");

  const [selPicksA, setSelPicksA] = useState<string[]>([]);
  const [selPicksB, setSelPicksB] = useState<string[]>([]);

  const [status, setStatus] = useState("");
  const [error, setError] = useState("");
  const [result, setResult] = useState<AnalysisResult | null>(null);
  const [mlMetricsAvailable, setMlMetricsAvailable] = useState(false);

  useEffect(() => {
    getMlMetrics()
      .then((m) => setMlMetricsAvailable(m.available === true))
      .catch(() => setMlMetricsAvailable(false));
  }, []);

  useEffect(() => {
    getSeasonConfig()
      .then((c) => setLeagueYear(c.league_year_end))
      .catch(() => {});
  }, []);

  useEffect(() => {
    getBrackets().then((b) => setBrackets(b.brackets)).catch(() => {});
  }, []);

  useEffect(() => {
    setTeamsLoading(true);
    getTeams()
      .then(({ teams: list }) => {
        setTeams(list);
        if (list.length === 0) return;
        let a = list.includes("OKC") ? "OKC" : list[0];
        let b = list.includes("DEN") ? "DEN" : list[Math.min(1, list.length - 1)];
        if (a === b) b = list.find((t) => t !== a) ?? b;
        setLabelA(a);
        setLabelB(b);
      })
      .catch(() => setTeams([]))
      .finally(() => setTeamsLoading(false));
  }, []);

  /** Ensure both sides never reference the same club. */
  useEffect(() => {
    if (teams.length < 2) return;
    const a = labelA.toUpperCase();
    const b = labelB.toUpperCase();
    if (a !== b) return;
    const alt = teams.find((t) => t !== a);
    if (alt) setLabelB(alt);
  }, [teams, labelA, labelB]);

  useEffect(() => {
    let cancel = false;
    setRosterLoadingA(true);
    getTeamRoster(labelA)
      .then((r) => {
        if (!cancel) setRosterA(r.players);
      })
      .catch(() => {
        if (!cancel) setRosterA([]);
      })
      .finally(() => {
        if (!cancel) setRosterLoadingA(false);
      });
    return () => {
      cancel = true;
    };
  }, [labelA]);

  useEffect(() => {
    let cancel = false;
    setRosterLoadingB(true);
    getTeamRoster(labelB)
      .then((r) => {
        if (!cancel) setRosterB(r.players);
      })
      .catch(() => {
        if (!cancel) setRosterB([]);
      })
      .finally(() => {
        if (!cancel) setRosterLoadingB(false);
      });
    return () => {
      cancel = true;
    };
  }, [labelB]);

  useEffect(() => {
    const ids = new Set(
      rosterA.map((p) => p.player_id).filter((x): x is number => typeof x === "number" && !Number.isNaN(x)),
    );
    setRosterSelA((s) => s.filter((id) => ids.has(id)));
  }, [rosterA]);

  useEffect(() => {
    const ids = new Set(
      rosterB.map((p) => p.player_id).filter((x): x is number => typeof x === "number" && !Number.isNaN(x)),
    );
    setRosterSelB((s) => s.filter((id) => ids.has(id)));
  }, [rosterB]);

  const optionsA = useMemo(() => teams.filter((t) => t !== labelB.toUpperCase()), [teams, labelB]);
  const optionsB = useMemo(() => teams.filter((t) => t !== labelA.toUpperCase()), [teams, labelA]);

  const setTeamA = useCallback(
    (code: string) => {
      const next = code.toUpperCase();
      setLabelA(next);
      if (next === labelB.toUpperCase() && teams.length > 1) {
        const alt = teams.find((t) => t !== next);
        if (alt) setLabelB(alt);
      }
    },
    [labelB, teams],
  );

  const setTeamB = useCallback(
    (code: string) => {
      const next = code.toUpperCase();
      setLabelB(next);
      if (next === labelA.toUpperCase() && teams.length > 1) {
        const alt = teams.find((t) => t !== next);
        if (alt) setLabelA(alt);
      }
    },
    [labelA, teams],
  );

  const loadPickLists = useCallback(() => {
    getPicks(leagueYear)
      .then((r) => setPickOptions(r.picks))
      .catch(() => {});
  }, [leagueYear]);

  useEffect(() => {
    loadPickLists();
  }, [loadPickLists]);

  /** Drop pick selections that no longer exist for this league year. */
  useEffect(() => {
    const ids = new Set(pickOptions.map((p) => p.id));
    setSelPicksA((s) => s.filter((id) => ids.has(id)));
    setSelPicksB((s) => s.filter((id) => ids.has(id)));
  }, [pickOptions]);

  const sameTeam = labelA.toUpperCase() === labelB.toUpperCase();

  const run = async () => {
    if (sameTeam || teams.length < 2) {
      setError("Select two different teams to run a trade.");
      return;
    }
    const playersA = mergeRosterAndManualLines(rosterSelA, manualA);
    const playersB = mergeRosterAndManualLines(rosterSelB, manualB);
    if (playersA.length === 0 || playersB.length === 0) {
      setError("Add at least one player per side using the roster list and/or manual lines.");
      return;
    }
    setError("");
    setStatus("Running…");
    setResult(null);
    try {
      const body = {
        league_year: leagueYear,
        team_a: {
          label: labelA,
          salary_bracket: bracketA,
          players: playersA,
          picks: selPicksA,
        },
        team_b: {
          label: labelB,
          salary_bracket: bracketB,
          players: playersB,
          picks: selPicksB,
        },
      };
      const out = await analyzeTrade(body);
      setResult(out);
      setStatus("");
    } catch (e) {
      setStatus("");
      setError(e instanceof Error ? e.message : String(e));
    }
  };

  const onReload = async () => {
    setError("");
    setStatus("Reloading CSV…");
    try {
      await reloadPool();
      const { teams: list } = await getTeams();
      setTeams(list);
      if (list.length >= 2) {
        let a = labelA.toUpperCase();
        let b = labelB.toUpperCase();
        if (!list.includes(a)) a = list[0]!;
        if (!list.includes(b)) b = list[Math.min(1, list.length - 1)]!;
        if (a === b) b = list.find((t) => t !== a) ?? b;
        setLabelA(a);
        setLabelB(b);
      }
      setStatus("Cache cleared. Next analysis loads fresh data.");
    } catch (e) {
      setError(e instanceof Error ? e.message : String(e));
      setStatus("");
    }
  };

  const downloadJson = () => {
    if (!result) return;
    const blob = new Blob([JSON.stringify(result, null, 2)], { type: "application/json" });
    const a = document.createElement("a");
    a.href = URL.createObjectURL(blob);
    a.download = "trade_analysis.json";
    a.click();
    URL.revokeObjectURL(a.href);
  };

  return (
    <div className="min-h-screen bg-app-gradient">
      <header className="relative overflow-hidden border-b border-white/[0.07] bg-gradient-to-b from-surface via-[#0c0e14] to-canvas">
        <div
          className="pointer-events-none absolute inset-0 bg-hero-shine opacity-90"
          aria-hidden
        />
        <div className="pointer-events-none absolute inset-0 bg-[url('data:image/svg+xml,%3Csvg width=\'72\' height=\'72\' viewBox=\'0 0 72 72\' xmlns=\'http://www.w3.org/2000/svg\'%3E%3Cg fill=\'none\' fill-rule=\'evenodd\'%3E%3Cg fill=\'%23ffffff\' fill-opacity=\'0.025\'%3E%3Cpath d=\'M36 34v-4h-2v4h-4v2h4v4h2v-4h4v-2h-4zm0-30V0h-2v4h-4v2h4v4h2V6h4V4h-4zM6 34v-4H4v4H0v2h4v4h2v-4h4v-2H6zM6 4V0H4v4H0v2h4v4h2V6h4V4H6z\'/%3E%3C/g%3E%3C/g%3E%3C/svg%3E')]" />
        <div className="relative mx-auto max-w-6xl px-4 py-12 sm:px-6">
          <div className="flex flex-wrap items-start justify-between gap-8">
            <div className="max-w-xl">
              <div className="flex items-center gap-3">
                <span className="flex h-11 w-11 items-center justify-center rounded-xl border border-white/10 bg-gradient-to-br from-accent/20 to-sideb/15 shadow-[0_0_24px_-4px_rgba(56,189,248,0.4)]">
                  <span className="text-lg font-bold text-gradient-brand" aria-hidden>
                    T
                  </span>
                </span>
                <p className="text-[11px] font-semibold uppercase tracking-[0.22em] text-accent">
                  NBA · trade desk
                </p>
              </div>
              <h1 className="mt-4 text-3xl font-bold tracking-tight text-ink sm:text-4xl sm:leading-tight">
                Professional <span className="text-gradient-brand">Trade Analyzer</span>
              </h1>
              <p className="mt-3 text-sm leading-relaxed text-muted">
                Salary-band checks, pick trade value, roster-aware packaging, and balance notes—modeled on your player
                pool.
                {mlMetricsAvailable && (
                  <span className="mt-2 block text-accentdim">
                    Offline ML scores (VORP regression) are merged into the pool—compare heuristic vs ML columns in
                    results.
                  </span>
                )}
              </p>
            </div>
            <div className="w-full max-w-sm rounded-2xl border border-white/[0.08] bg-surface2/80 px-5 py-4 text-xs shadow-card backdrop-blur-md sm:w-auto">
              <p className="font-semibold uppercase tracking-wide text-ink2">Local stack</p>
              <p className="mt-2 font-mono text-[11px] leading-relaxed text-muted">
                <span className="text-accentdim">api</span> uvicorn webapp:app —port 8000
                <br />
                <span className="text-sideb">ui</span> npm run dev → :5173
              </p>
            </div>
          </div>
        </div>
      </header>

      <main className="mx-auto max-w-6xl px-4 py-10 sm:px-6">
        <section className="rounded-2xl border border-white/[0.06] bg-surface/75 p-6 shadow-lift backdrop-blur-xl sm:p-8">
          <div className="flex flex-wrap items-end justify-between gap-4 border-b border-line pb-6">
            <div>
              <h2 className="text-lg font-semibold tracking-tight text-ink">Build trade</h2>
              <p className="mt-1.5 text-sm text-muted">
                Roster multi-select or manual lines:{" "}
                <code className="rounded-md border border-white/10 bg-elevated px-1.5 py-0.5 font-mono text-[11px] text-accent">
                  Name|TEAM
                </code>{" "}
                ·{" "}
                <code className="rounded-md border border-white/10 bg-elevated px-1.5 py-0.5 font-mono text-[11px] text-accent">
                  id:2544
                </code>
              </p>
              <p className="mt-2 text-xs text-muted">
                <span className="font-medium text-ink2">Season end year</span> filters draft picks to future classes
                only.
              </p>
            </div>
            <label className="flex flex-col gap-1.5 text-sm">
              <span className="font-medium text-muted">Season end year (pick TV)</span>
              <input
                type="number"
                value={leagueYear}
                onChange={(e) => setLeagueYear(parseInt(e.target.value, 10) || 2025)}
                className="w-28 rounded-xl border border-line bg-elevated px-3 py-2.5 font-mono text-sm text-ink shadow-inset outline-none ring-accent/20 transition focus:border-accent/40 focus:ring-2"
              />
            </label>
          </div>

          <div className="mt-8 grid gap-8 lg:grid-cols-2">
            <SidePanel
              variant="a"
              teamOptions={optionsA}
              teamValue={labelA}
              onTeamChange={setTeamA}
              teamsLoading={teamsLoading}
              bracket={bracketA}
              onBracket={setBracketA}
              brackets={brackets}
              rosterPlayers={rosterA}
              rosterLoading={rosterLoadingA}
              rosterSelectedIds={rosterSelA}
              onRosterSelectedIds={setRosterSelA}
              manualText={manualA}
              onManualText={setManualA}
              picks={pickOptions}
              sel={selPicksA}
              onSel={setSelPicksA}
            />
            <SidePanel
              variant="b"
              teamOptions={optionsB}
              teamValue={labelB}
              onTeamChange={setTeamB}
              teamsLoading={teamsLoading}
              bracket={bracketB}
              onBracket={setBracketB}
              brackets={brackets}
              rosterPlayers={rosterB}
              rosterLoading={rosterLoadingB}
              rosterSelectedIds={rosterSelB}
              onRosterSelectedIds={setRosterSelB}
              manualText={manualB}
              onManualText={setManualB}
              picks={pickOptions}
              sel={selPicksB}
              onSel={setSelPicksB}
            />
          </div>

          <div className="mt-8 flex flex-wrap items-center gap-3 border-t border-line pt-6">
            <button
              type="button"
              disabled={sameTeam || teams.length < 2 || teamsLoading}
              onClick={() => void run()}
              className="rounded-xl bg-gradient-to-r from-sky-500 to-cyan-500 px-6 py-3 text-sm font-semibold text-slate-950 shadow-[0_0_20px_-4px_rgba(56,189,248,0.55)] transition hover:brightness-110 disabled:cursor-not-allowed disabled:opacity-40"
            >
              Run analysis
            </button>
            <button
              type="button"
              onClick={() => void onReload()}
              className="rounded-xl border border-white/10 bg-elevated px-5 py-3 text-sm font-medium text-ink2 shadow-inset transition hover:border-white/15 hover:bg-surface2"
            >
              Reload data
            </button>
            {sameTeam && teams.length >= 2 && (
              <span className="text-sm text-amber-400/95" role="status">
                Both sides cannot be the same team.
              </span>
            )}
            {status && <span className="text-sm text-muted">{status}</span>}
            {error && (
              <span className="text-sm text-red-400" role="alert">
                {error}
              </span>
            )}
          </div>
        </section>

        {result && (
          <div className="mt-12">
            <div className="mb-6 flex items-center gap-3">
              <span className="h-px flex-1 bg-gradient-to-r from-transparent via-line to-transparent" />
              <h2 className="text-xs font-semibold uppercase tracking-[0.2em] text-muted">Analysis</h2>
              <span className="h-px flex-1 bg-gradient-to-r from-transparent via-line to-transparent" />
            </div>
            <ResultsView data={result} onDownloadJson={downloadJson} />
          </div>
        )}

        <footer className="mt-16 border-t border-white/[0.05] pt-8 text-center text-[11px] text-muted">
          Illustrative analytics only. Not legal or financial advice.
        </footer>
      </main>
    </div>
  );
}

function SidePanel({
  variant,
  teamOptions,
  teamValue,
  onTeamChange,
  teamsLoading,
  bracket,
  onBracket,
  brackets,
  rosterPlayers,
  rosterLoading,
  rosterSelectedIds,
  onRosterSelectedIds,
  manualText,
  onManualText,
  picks,
  sel,
  onSel,
}: {
  variant: "a" | "b";
  teamOptions: string[];
  teamValue: string;
  onTeamChange: (code: string) => void;
  teamsLoading: boolean;
  bracket: string;
  onBracket: (v: string) => void;
  brackets: Array<{ id: string; short_label: string; multiplier: number; cushion_mm: number }>;
  rosterPlayers: RosterPlayer[];
  rosterLoading: boolean;
  rosterSelectedIds: number[];
  onRosterSelectedIds: (ids: number[]) => void;
  manualText: string;
  onManualText: (v: string) => void;
  picks: Array<{ id: string; label: string; trade_value: number }>;
  sel: string[];
  onSel: (ids: string[]) => void;
}) {
  const isA = variant === "a";
  const bar = isA ? "from-sky-400 via-cyan-400 to-sky-500" : "from-violet-400 via-indigo-400 to-violet-500";
  const soft = isA
    ? "border-sky-400/20 bg-gradient-to-br from-accentsoft/40 to-surface2/90"
    : "border-sideb/25 bg-gradient-to-br from-sidebsoft/35 to-surface2/90";
  const badge = isA
    ? "border-sky-400/30 bg-accentsoft text-accent ring-sky-400/25"
    : "border-sideb/30 bg-sidebsoft text-sideb ring-sideb/25";

  const rosterWithIds = useMemo(
    () => rosterPlayers.filter((p) => typeof p.player_id === "number" && !Number.isNaN(p.player_id)),
    [rosterPlayers],
  );

  return (
    <div className={`relative overflow-hidden rounded-2xl border ${soft} p-6 shadow-card`}>
      <div className={`absolute left-0 top-0 h-full w-1 bg-gradient-to-b ${bar}`} aria-hidden />
      <div className="pointer-events-none absolute -right-16 -top-16 h-40 w-40 rounded-full bg-gradient-to-br from-white/[0.04] to-transparent blur-2xl" />
      <div className="relative">
        <div className="mb-5 flex flex-wrap items-center gap-3">
          <span
            className={`inline-flex items-center rounded-full border px-3 py-1 text-[11px] font-bold uppercase tracking-wider ring-1 ${badge}`}
          >
            Side {isA ? "A" : "B"} · Sending
          </span>
          {teamsLoading && <span className="text-xs text-muted">Loading teams…</span>}
        </div>

        <label className="block text-sm font-medium text-ink2">
          Franchise
          <select
            className="team-select mt-2 w-full appearance-none rounded-xl border border-line bg-elevated px-3 py-3 text-sm font-semibold text-ink shadow-inset outline-none ring-accent/15 transition focus:border-accent/35 focus:ring-2 disabled:opacity-50"
            value={teamValue.toUpperCase()}
            disabled={teamsLoading || teamOptions.length === 0}
            onChange={(e) => onTeamChange(e.target.value)}
          >
            {teamOptions.map((code) => (
              <option key={code} value={code}>
                {teamOptionLabel(code)}
              </option>
            ))}
          </select>
        </label>
        <p className="mt-1.5 text-xs text-muted">
          Opponent is hidden from this list so you can&apos;t mirror the same club on both sides.
        </p>

        <label className="mt-5 block text-sm font-medium text-ink2">
          Salary band
          <select
            value={bracket}
            onChange={(e) => onBracket(e.target.value)}
            className="team-select mt-2 w-full appearance-none rounded-xl border border-line bg-elevated px-3 py-3 text-sm text-ink2 shadow-inset outline-none ring-accent/15 transition focus:border-accent/35 focus:ring-2"
          >
            {brackets.map((b) => (
              <option key={b.id} value={b.id}>
                {b.short_label} (~{b.multiplier}× + ${b.cushion_mm}M)
              </option>
            ))}
          </select>
        </label>

        <label className="mt-5 block text-sm font-medium text-ink2">
          Players on {teamValue.toUpperCase()} (Ctrl/Cmd + click for multi-select)
          <select
            multiple
            size={Math.min(12, Math.max(5, rosterWithIds.length || 5))}
            value={rosterSelectedIds.map(String)}
            disabled={rosterLoading || rosterWithIds.length === 0}
            onChange={(e) =>
              onRosterSelectedIds(Array.from(e.target.selectedOptions).map((o) => parseInt(o.value, 10)))
            }
            className="mt-2 w-full rounded-xl border border-line bg-[#0d1018] px-2 py-2 font-mono text-xs text-ink shadow-inset outline-none ring-accent/15 transition focus:border-accent/35 focus:ring-2 disabled:opacity-50 sm:text-sm"
          >
            {rosterWithIds.map((p) => (
              <option key={p.player_id} value={String(p.player_id)}>
                {p.player_name} · H {p.trade_value_score}
                {p.ml_value_score != null ? ` · ML ${p.ml_value_score}` : ""} · ${p.salary_mm}M
              </option>
            ))}
          </select>
        </label>
        {rosterLoading && <p className="mt-1 text-xs text-muted">Loading roster…</p>}
        {!rosterLoading && rosterWithIds.length === 0 && (
          <p className="mt-1 text-xs text-amber-400/90">No roster rows with player IDs for this team—use manual lines.</p>
        )}
        {!rosterLoading && rosterWithIds.length > 0 && (
          <p className="mt-1 text-xs text-muted">{rosterSelectedIds.length} selected from roster</p>
        )}

        <label className="mt-5 block text-sm font-medium text-ink2">
          Manual add (optional, appended after roster)
          <textarea
            value={manualText}
            onChange={(e) => onManualText(e.target.value)}
            rows={3}
            placeholder="e.g. Gilgeous-Alexander or id:1628983"
            className="mt-2 w-full rounded-xl border border-line bg-elevated px-3 py-3 font-mono text-sm text-ink placeholder:text-muted/60 shadow-inset outline-none ring-accent/15 transition focus:border-accent/35 focus:ring-2"
          />
        </label>

        <label className="mt-5 block text-sm font-medium text-ink2">
          Draft picks (multi-select)
          {picks.length === 0 ? (
            <p className="mt-2 rounded-xl border border-amber-500/25 bg-amber-500/10 px-3 py-2.5 text-xs text-amber-200/95">
              No picks left for this season year in the catalog. Try a lower year or add picks in{" "}
              <code className="font-mono text-amber-300">picks.py</code>.
            </p>
          ) : (
            <select
              multiple
              size={7}
              value={sel}
              onChange={(e) => onSel(Array.from(e.target.selectedOptions).map((o) => o.value))}
              className="mt-2 w-full rounded-xl border border-line bg-[#0d1018] px-2 py-2 text-sm text-ink2 shadow-inset outline-none ring-accent/15 transition focus:border-accent/35 focus:ring-2"
            >
              {picks.map((p) => (
                <option key={p.id} value={p.id}>
                  {p.label} (TV {p.trade_value})
                </option>
              ))}
            </select>
          )}
        </label>
      </div>
    </div>
  );
}
