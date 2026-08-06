import type { AgentResult, ResearchWindows } from '../types/pipeline'

function fmtSharpe(x: number | null | undefined): string {
  if (x == null || Number.isNaN(x)) return '—'
  return x.toFixed(3)
}

function fmtUtil(x: number | null | undefined): string {
  if (x == null || Number.isNaN(x)) return '—'
  return x.toFixed(3)
}

function WindowsStrip({ windows }: { windows?: ResearchWindows | null }) {
  if (!windows?.train) return null
  const cell = (label: string, w: { start?: string | null; end?: string | null } | null | undefined) =>
    w?.start && w?.end ? (
      <span>
        <span className="text-muted">{label} </span>
        <span className="text-ink">
          {w.start}→{w.end}
        </span>
      </span>
    ) : null
  return (
    <p className="font-mono text-[11px] text-muted">
      {cell('Train', windows.train)}
      <span className="mx-1.5 text-line">·</span>
      {cell('Val', windows.val)}
      <span className="mx-1.5 text-line">·</span>
      {cell('Test', windows.test)}
    </p>
  )
}

export function AgentHistory({ data }: { data: AgentResult }) {
  const ranked = data.leaderboard?.length
    ? data.leaderboard
    : [...data.iterations]
        .map((it) => ({
          iteration: it.iteration,
          name: it.name || `#${it.iteration}`,
          template: it.template,
          test_utility: it.utility ?? null,
          test_sharpe: it.test_sharpe,
          test_hit: it.test_summary?.signal_hit_rate ?? null,
          code_hash: it.code_hash,
        }))
        .sort((a, b) => (b.test_utility ?? -999) - (a.test_utility ?? -999))

  const curve = data.utility_curve || []

  return (
    <div className="space-y-5">
      <div className="space-y-1">
        <p className="font-mono text-xs text-muted">
          {data.horizon}
          <span className="mx-2 text-line">·</span>
          best #{data.best_iteration}
          <span className="mx-2 text-line">·</span>
          test Sharpe {fmtSharpe(data.best_test_sharpe)}
          <span className="mx-2 text-line">·</span>
          util {fmtUtil(data.best_test_utility)}
        </p>
        <WindowsStrip windows={data.research_windows} />
      </div>

      {ranked.length > 0 ? (
        <div>
          <h3 className="mb-2 text-[11px] font-medium uppercase tracking-wide text-muted">
            Leaderboard
          </h3>
          <div className="overflow-x-auto">
            <table className="w-full text-left text-sm">
              <thead>
                <tr className="border-b border-line text-[11px] uppercase tracking-wide text-muted">
                  <th className="pb-2 pr-3 font-medium">#</th>
                  <th className="pb-2 pr-3 font-medium">Name</th>
                  <th className="pb-2 pr-3 font-medium">Utility</th>
                  <th className="pb-2 pr-3 font-medium">Sharpe</th>
                  <th className="pb-2 font-medium">Hit</th>
                </tr>
              </thead>
              <tbody className="font-mono text-[12px]">
                {ranked.map((r) => (
                  <tr
                    key={`${r.iteration}-${r.code_hash}`}
                    className={[
                      'border-b border-line/70 last:border-0',
                      r.iteration === data.best_iteration ? 'bg-teal-soft/10' : '',
                    ].join(' ')}
                  >
                    <td className="py-2 pr-3">{r.iteration}</td>
                    <td className="py-2 pr-3 font-sans text-ink">
                      {r.name || r.template}
                    </td>
                    <td className="py-2 pr-3">{fmtUtil(r.test_utility)}</td>
                    <td className="py-2 pr-3">{fmtSharpe(r.test_sharpe)}</td>
                    <td className="py-2">
                      {r.test_hit != null ? `${(r.test_hit * 100).toFixed(1)}%` : '—'}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>
      ) : null}

      {curve.length > 1 ? (
        <div>
          <h3 className="mb-2 text-[11px] font-medium uppercase tracking-wide text-muted">
            Utility curve
          </h3>
          <div className="flex h-16 items-end gap-1">
            {curve.map((p) => {
              const h = Math.max(8, Math.min(64, (p.utility || 0) * 64))
              return (
                <div
                  key={p.iteration}
                  title={`#${p.iteration} util=${p.utility?.toFixed(3)}`}
                  className="flex-1 rounded-t bg-teal/70"
                  style={{ height: h }}
                />
              )
            })}
          </div>
        </div>
      ) : null}

      <ol className="space-y-3">
        {data.iterations.map((it) => {
          const best = it.iteration === data.best_iteration
          return (
            <li
              key={it.iteration}
              className={[
                'rounded-lg border px-4 py-3',
                best ? 'border-teal/40 bg-teal-soft/10' : 'border-line bg-white/50',
              ].join(' ')}
            >
              <div className="flex flex-wrap items-baseline justify-between gap-2">
                <p className="text-sm font-semibold text-ink">
                  #{it.iteration}
                  {best ? <span className="ml-2 text-xs font-medium text-teal">best</span> : null}
                  <span className="ml-2 font-normal text-muted">
                    {it.name || it.template}
                  </span>
                </p>
                <p className="font-mono text-[11px] text-muted">
                  tr {fmtSharpe(it.train_sharpe)}
                  {it.val_sharpe != null ? ` · va ${fmtSharpe(it.val_sharpe)}` : ''}
                  {' · '}te {fmtSharpe(it.test_sharpe)}
                  {it.utility != null ? ` · util ${fmtUtil(it.utility)}` : ''}
                </p>
              </div>
              <p className="mt-2 text-sm leading-snug text-ink/85">{it.hypothesis}</p>
              {it.insights ? (
                <p className="mt-2 text-xs leading-relaxed text-muted">{it.insights}</p>
              ) : null}

              {it.portfolios && Object.keys(it.portfolios).length > 0 ? (
                <div className="mt-3 overflow-x-auto">
                  <table className="w-full text-left font-mono text-[11px]">
                    <thead>
                      <tr className="text-muted">
                        <th className="pb-1 pr-2 font-medium">Book</th>
                        <th className="pb-1 pr-2 font-medium">Test hit</th>
                        <th className="pb-1 pr-2 font-medium">ARR</th>
                        <th className="pb-1 font-medium">Util</th>
                      </tr>
                    </thead>
                    <tbody>
                      {Object.entries(it.portfolios).map(([pname, block]) => {
                        const b = block as { test?: Record<string, number>; n_stocks?: number }
                        const t = b.test || {}
                        return (
                          <tr key={pname} className="border-t border-line/50">
                            <td className="py-1 pr-2 font-sans">
                              {pname}
                              {b.n_stocks != null ? ` (${b.n_stocks})` : ''}
                            </td>
                            <td className="py-1 pr-2">
                              {t.signal_hit_rate != null
                                ? `${(t.signal_hit_rate * 100).toFixed(1)}%`
                                : '—'}
                            </td>
                            <td className="py-1 pr-2">
                              {t.annualized_return != null
                                ? `${(t.annualized_return * 100).toFixed(1)}%`
                                : '—'}
                            </td>
                            <td className="py-1">{fmtUtil(t.utility)}</td>
                          </tr>
                        )
                      })}
                    </tbody>
                  </table>
                </div>
              ) : null}
            </li>
          )
        })}
      </ol>
    </div>
  )
}
