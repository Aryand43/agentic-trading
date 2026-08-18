import { AgentHistory } from './AgentHistory'
import { HintLabel } from './Hint'
import { HINTS } from '../content/hints'
import type { AgentResult } from '../types/pipeline'

export function AgentPanel({ data }: { data: AgentResult }) {
  return (
    <section className="space-y-3 border-t border-line pt-6 animate-[fadeIn_0.35s_ease-out]">
      <div>
        <h2 className="text-lg font-semibold tracking-tight text-ink">
          <HintLabel label="Agent" text={HINTS.agentHistory} />
        </h2>
        <p className="mt-0.5 text-sm text-muted">Iterations by out-of-sample Sharpe</p>
      </div>
      <AgentHistory data={data} />
    </section>
  )
}
