import type { AnalysisResult } from "./api";
import { ChartsBlock } from "./ChartsBlock";

export function ResultsView({
  data,
  onDownloadJson,
}: {
  data: AnalysisResult;
  onDownloadJson: () => void;
}) {
  const sal = data.salary as Record<string, string | number | boolean>;
  const tv = data.trade_value as Record<string, number | undefined>;
  const v = data.verdict as Record<string, string>;
  const vm = data.verdict_ml as Record<string, string> | null | undefined;
  const meta = data.meta as Record<string, string | boolean> | undefined;

  const legal = sal.trade_legal === true;
  const mlLoaded = meta?.ml_scores_loaded === true;

  return (
    <div className="space-y-6">
      <div className="flex flex-wrap items-center gap-3">
        <button
          type="button"
          onClick={onDownloadJson}
          className="rounded-xl border border-white/10 bg-elevated px-4 py-2.5 text-sm font-medium text-ink2 shadow-inset transition hover:border-white/18 hover:bg-surface2"
        >
          Download JSON
        </button>
      </div>

      <div className="grid gap-4 md:grid-cols-2">
        <section className="rounded-2xl border border-white/[0.06] bg-surface/80 p-5 shadow-card backdrop-blur-sm">
          <h3 className="text-sm font-semibold uppercase tracking-wide text-muted">Salary matching</h3>
          <dl className="mt-4 grid gap-2 text-sm sm:grid-cols-2">
            <Stat k="Side A band" v={`${String(sal.team_a_band)} (${sal.team_a_multiplier}× + $${sal.team_a_cushion_mm}M)`} />
            <Stat k="Side B band" v={`${String(sal.team_b_band)} (${sal.team_b_multiplier}× + $${sal.team_b_cushion_mm}M)`} />
            <Stat k={`${data.team_a_label} outgoing`} v={`$${sal.team_a_outgoing_mm}M`} />
            <Stat k={`${data.team_b_label} outgoing`} v={`$${sal.team_b_outgoing_mm}M`} />
            <Stat k={`${data.team_a_label} max send`} v={`$${sal.team_a_max_outgoing_mm}M`} />
            <Stat k={`${data.team_b_label} max send`} v={`$${sal.team_b_max_outgoing_mm}M`} />
          </dl>
          <p
            className={`mt-4 rounded-xl border px-3 py-3 text-sm leading-snug ${
              legal
                ? "border-emerald-500/30 bg-emerald-500/10 text-emerald-100"
                : "border-red-500/35 bg-red-500/10 text-red-200"
            }`}
          >
            {String(sal.disclaimer ?? (legal ? "Bands satisfied on this model." : "At least one side fails its band."))}
          </p>
        </section>

        <section className="rounded-2xl border border-white/[0.06] bg-surface/80 p-5 shadow-card backdrop-blur-sm">
          <h3 className="text-sm font-semibold uppercase tracking-wide text-muted">Trade value</h3>
          <dl className="mt-4 grid gap-2 text-sm">
            <Stat
              k={`${data.team_a_label} total`}
              v={`${tv.team_a_total} (pl ${tv.team_a_from_players} + pk ${tv.team_a_from_picks})`}
            />
            <Stat
              k={`${data.team_b_label} total`}
              v={`${tv.team_b_total} (pl ${tv.team_b_from_players} + pk ${tv.team_b_from_picks})`}
            />
            <Stat k="Surplus (A − B)" v={String(tv.surplus_for_team_a)} />
            {meta?.trade_value_blend && <Stat k="Blend" v={String(meta.trade_value_blend)} />}
            {mlLoaded && tv.team_a_total_ml != null && (
              <>
                <Stat
                  k={`${data.team_a_label} total (ML 0–100)`}
                  v={`${tv.team_a_total_ml} (pl ${tv.team_a_from_players_ml} + pk ${tv.team_a_from_picks})`}
                />
                <Stat
                  k={`${data.team_b_label} total (ML 0–100)`}
                  v={`${tv.team_b_total_ml} (pl ${tv.team_b_from_players_ml} + pk ${tv.team_b_from_picks})`}
                />
                <Stat k="Surplus ML (A − B)" v={String(tv.surplus_for_team_a_ml)} />
              </>
            )}
          </dl>
          {meta?.ml_model_note && (
            <p className="mt-3 rounded-xl border border-sky-500/20 bg-sky-500/5 px-3 py-2.5 text-xs leading-relaxed text-muted">
              {String(meta.ml_model_note)}
            </p>
          )}
        </section>
      </div>

      <section className="rounded-2xl border border-white/[0.06] bg-surface/80 p-5 shadow-card backdrop-blur-sm">
        <h3 className="text-sm font-semibold uppercase tracking-wide text-muted">Balancing ideas</h3>
        <ul className="mt-4 divide-y divide-white/[0.06]">
          {(data.balance_suggestions ?? []).map((s, i) => (
            <li key={i} className="py-4 first:pt-0">
              <p className="text-[10px] font-bold uppercase tracking-[0.15em] text-accent">{s.category}</p>
              <p className="mt-1 font-semibold text-ink">{s.title}</p>
              <p className="mt-1.5 text-sm leading-relaxed text-muted">{s.detail}</p>
            </li>
          ))}
          {(!data.balance_suggestions || data.balance_suggestions.length === 0) && (
            <li className="py-3 text-sm text-muted">No extra notes.</li>
          )}
        </ul>
      </section>

      <section className="rounded-2xl border border-white/[0.06] bg-surface/80 p-5 shadow-card backdrop-blur-sm">
        <h3 className="text-sm font-semibold uppercase tracking-wide text-muted">Roster &amp; assets</h3>
        <div className="mt-4 overflow-x-auto rounded-xl border border-white/[0.05]">
          <table className="w-full min-w-[900px] border-collapse text-left text-sm">
            <thead>
              <tr className="border-b border-line bg-elevated text-[10px] font-semibold uppercase tracking-wider text-muted">
                <th className="px-3 py-2.5">Side</th>
                <th className="px-3 py-2.5">Asset</th>
                <th className="px-3 py-2.5">Team</th>
                <th className="px-3 py-2.5">Age</th>
                <th className="px-3 py-2.5">$M</th>
                <th className="px-3 py-2.5">Yrs</th>
                <th className="px-3 py-2.5">TV (H)</th>
                <th className="px-3 py-2.5">ML</th>
                <th className="px-3 py-2.5">Hyb</th>
                <th className="px-3 py-2.5">Talent</th>
                <th className="px-3 py-2.5">C.</th>
                <th className="px-3 py-2.5">Match</th>
                <th className="px-3 py-2.5">PTS</th>
                <th className="px-3 py-2.5">AST</th>
                <th className="px-3 py-2.5">REB</th>
              </tr>
            </thead>
            <tbody className="text-ink2">
              {data.profiles.map((p, i) => {
                const pick = p.asset_type === "pick";
                return (
                  <tr
                    key={i}
                    className={`border-b border-white/[0.04] transition hover:bg-white/[0.02] ${pick ? "text-accent" : ""}`}
                  >
                    <td className="px-3 py-2">{String(p.side)}</td>
                    <td className="px-3 py-2">{String(p.player_name)}</td>
                    <td className="px-3 py-2">{p.team != null ? String(p.team) : ""}</td>
                    <td className="px-3 py-2">{fmt(p.age, 1)}</td>
                    <td className="px-3 py-2">{fmt(p.salary_mm, 2)}</td>
                    <td className="px-3 py-2">
                      {p.contract_years_remaining != null ? String(p.contract_years_remaining) : "—"}
                    </td>
                    <td className="px-3 py-2">{fmt(p.trade_value_score, 1)}</td>
                    <td className="px-3 py-2">{fmt(p.ml_value_score, 1)}</td>
                    <td className="px-3 py-2">{fmt(p.trade_value_hybrid, 1)}</td>
                    <td className="px-3 py-2">{fmt(p.talent_score, 1)}</td>
                    <td className="px-3 py-2">{fmt(p.contract_value_score, 1)}</td>
                    <td className="px-3 py-2">
                      {p.aggregation_salary_mm != null && typeof p.aggregation_salary_mm === "number"
                        ? p.aggregation_salary_mm.toFixed(2)
                        : "—"}
                    </td>
                    <td className="px-3 py-2">{fmt(p.pts, 1)}</td>
                    <td className="px-3 py-2">{fmt(p.ast, 1)}</td>
                    <td className="px-3 py-2">{fmt(p.reb, 1)}</td>
                  </tr>
                );
              })}
            </tbody>
          </table>
        </div>
      </section>

      <ChartsBlock data={data} />

      <section className="rounded-2xl border border-white/[0.06] bg-surface/80 p-5 shadow-card backdrop-blur-sm">
        <h3 className="text-sm font-semibold uppercase tracking-wide text-muted">Verdict (heuristic TV)</h3>
        <p className="mt-3 font-medium leading-relaxed text-ink">
          Value lean: {String(v.verdict_team)}. {String(v.salary_cap_note)}
        </p>
        <p className="mt-2 text-sm leading-relaxed text-muted">{String(v.reason)}</p>
        {vm && (
          <>
            <h4 className="mt-6 text-xs font-semibold uppercase tracking-wide text-accent">Verdict (offline ML TV)</h4>
            <p className="mt-2 font-medium leading-relaxed text-ink">
              Value lean: {String(vm.verdict_team)}. {String(vm.salary_cap_note)}
            </p>
            <p className="mt-2 text-sm leading-relaxed text-muted">{String(vm.reason)}</p>
          </>
        )}
      </section>
    </div>
  );
}

function Stat({ k, v }: { k: string; v: string }) {
  return (
    <div className="rounded-xl border border-white/[0.06] bg-elevated/80 px-3 py-2.5 shadow-inset">
      <dt className="text-[10px] font-bold uppercase tracking-wide text-muted">{k}</dt>
      <dd className="mt-1 font-medium text-ink">{v}</dd>
    </div>
  );
}

function fmt(v: unknown, d: number): string {
  if (v == null || typeof v !== "number") return "—";
  return v.toFixed(d);
}
