import { Hint } from './Hint'
import { fmtNum, fmtPct } from '../lib/format'
import { sparkScale } from '../lib/charts'
import type { AgentResult, ResearchWindows } from '../types/pipeline'

function WindowsStrip({ windows }: { windows?: ResearchWindows | null }) {
  if (!windows?.train) return null
  const cell = (
    label: string,
    w: { start?: string | null; end?: string | null } | null | undefined,
  ) =>
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

/** Per-iteration utility, drawn from a real zero baseline.
 *
 * The previous version floored every bar at 8 of 64 pixels, so a zero or
 * negative utility looked identical to a small positive one — the failing
 * iterations were the ones you could least afford to misread.
 */
function UtilityCurve({ points }: { points: { iteration: number; utility?: number }[] }) {
  const scale = sparkScale(points.map((p) => p.utility))

  return (
    <div>
      <h3 className="mb-2 text-[11px] font-medium uppercase tracking-wide text-muted">
        Utility curve
      </h3>
      <div className="relative h-16 w-full">
        <div
          aria-hidden
          className="absolute inset-x-0 border-t border-dashed border-line"
          style={{ top: `${scale.zero * 100}%` }}
        />
        <div className="absolute inset-0 flex items-stretch gap-1">
          {points.map((p, i) => {
            const bar = scale.bars[i]
            return (
              <Hint
                key={p.iteration}
                text={`Iteration ${p.iteration}: utility ${fmtNum(p.utility, 3)}`}
                className="relative flex-1"
                side="top"
              >
                <span
                  className={`absolute inset-x-0 cursor-help rounded-sm ${
                    bar.negative ? 'bg-rose/70' : 'bg-teal/70'
                  }`}
                  style={{ top: `${bar.fromTop * 100}%`, height: `${bar.height * 100}%` }}
                />
              </Hint>
            )
          })}
        </div>
      </div>
    </div>
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
          test Sharpe {fmtNum(data.best_test_sharpe, 3)}
          <span className="mx-2 text-line">·</span>
          util {fmtNum(data.best_test_utility, 3)}
        </p>
        <WindowsStrip windows={data.research_windows} />
      </div>

      {ranked.length > 0 ? (
        <div>
          <h3 className="mb-2 text-[11px] font-medium uppercase tracking-wide text-muted">
            Leaderboard
          </h3>
          <div className="overflow-x-auto">
            <table className="w-full min-w-105 text-left text-sm">
              <thead>
                <tr className="border-b border-line text-[11px] uppercase tracking-wide text-muted">
                  <th scope="col" className="pb-2 pr-3 font-medium">
                    #
                  </th>
                  <th scope="col" className="pb-2 pr-3 font-medium">
                    Name
                  </th>
                  <th scope="col" className="pb-2 pr-3 text-right font-medium">
                    Utility
                  </th>
                  <th scope="col" className="pb-2 pr-3 text-right font-medium">
                    Sharpe
                  </th>
                  <th scope="col" className="pb-2 text-right font-medium">
                    Hit
                  </th>
                </tr>
              </thead>
              <tbody className="font-mono text-[12px] tabular-nums">
                {ranked.map((r) => (
                  <tr
                    key={`${r.iteration}-${r.code_hash}`}
                    className={[
                      'border-b border-line/70 last:border-0',
                      r.iteration === data.best_iteration ? 'bg-teal-soft/10' : '',
                    ].join(' ')}
                  >
                    <td className="py-2 pr-3">{r.iteration}</td>
                    <th scope="row" className="py-2 pr-3 text-left font-sans font-normal text-ink">
                      {r.name || r.template}
                    </th>
                    <td className="py-2 pr-3 text-right">{fmtNum(r.test_utility, 3)}</td>
                    <td className="py-2 pr-3 text-right">{fmtNum(r.test_sharpe, 3)}</td>
                    <td className="py-2 text-right">{fmtPct(r.test_hit)}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>
      ) : null}

      {curve.length > 1 ? <UtilityCurve points={curve} /> : null}

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
                  <span className="ml-2 font-normal text-muted">{it.name || it.template}</span>
                </p>
                <p className="font-mono text-[11px] tabular-nums text-muted">
                  tr {fmtNum(it.train_sharpe, 3)}
                  {it.val_sharpe != null ? ` · va ${fmtNum(it.val_sharpe, 3)}` : ''}
                  {' · '}te {fmtNum(it.test_sharpe, 3)}
                  {it.utility != null ? ` · util ${fmtNum(it.utility, 3)}` : ''}
                </p>
              </div>
              <p className="mt-2 text-sm leading-snug text-ink/85">{it.hypothesis}</p>
              {it.insights ? (
                <p className="mt-2 text-xs leading-relaxed text-muted">{it.insights}</p>
              ) : null}

              {it.portfolios && Object.keys(it.portfolios).length > 0 ? (
                <div className="mt-3 overflow-x-auto">
                  <table className="w-full text-left font-mono text-[11px] tabular-nums">
                    <thead>
                      <tr className="text-muted">
                        <th scope="col" className="pb-1 pr-2 font-medium">
                          Book
                        </th>
                        <th scope="col" className="pb-1 pr-2 text-right font-medium">
                          Test hit
                        </th>
                        <th scope="col" className="pb-1 pr-2 text-right font-medium">
                          ARR
                        </th>
                        <th scope="col" className="pb-1 text-right font-medium">
                          Util
                        </th>
                      </tr>
                    </thead>
                    <tbody>
                      {Object.entries(it.portfolios).map(([pname, block]) => {
                        const b = block as { test?: Record<string, number>; n_stocks?: number }
                        const t = b.test || {}
                        return (
                          <tr key={pname} className="border-t border-line/50">
                            <th scope="row" className="py-1 pr-2 text-left font-sans font-normal">
                              {pname}
                              {b.n_stocks != null ? ` (${b.n_stocks})` : ''}
                            </th>
                            <td className="py-1 pr-2 text-right">{fmtPct(t.signal_hit_rate)}</td>
                            <td className="py-1 pr-2 text-right">{fmtPct(t.annualized_return)}</td>
                            <td className="py-1 text-right">{fmtNum(t.utility, 3)}</td>
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
