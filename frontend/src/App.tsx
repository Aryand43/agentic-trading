import { useState, type ReactNode } from 'react'
import { ConvictionChart } from './components/ConvictionChart'
import { HintLabel } from './components/Hint'
import { HorizonGrid } from './components/HorizonGrid'
import { MetaStrip } from './components/MetaStrip'
import { RunControls } from './components/RunControls'
import { WeightsChart } from './components/WeightsChart'
import { HINTS } from './content/hints'
import { usePipeline } from './hooks/usePipeline'

function parseTickers(raw: string): string[] {
  return raw
    .split(/[\s,]+/)
    .map((t) => t.trim().toUpperCase())
    .filter(Boolean)
}

export default function App() {
  const { data, loading, error, run } = usePipeline()
  const [tickersInput, setTickersInput] = useState('AAPL, MSFT, NVDA')
  const [maxPosition, setMaxPosition] = useState(0.15)

  const handleRun = () => {
    const tickers = parseTickers(tickersInput)
    void run({
      tickers: tickers.length ? tickers : null,
      max_position: maxPosition,
      gross_exposure: 1.0,
    })
  }

  return (
    <div className="mx-auto flex min-h-screen max-w-6xl flex-col gap-8 px-5 py-10 sm:px-8">
      <header className="flex flex-col gap-2">
        <p className="font-mono text-xs uppercase tracking-[0.2em] text-teal">Agentic Trading</p>
        <h1 className="text-3xl font-semibold tracking-tight text-ink sm:text-4xl">
          Pipeline desk
        </h1>
        <p className="max-w-xl text-sm leading-relaxed text-muted sm:text-base">
          Run the live signal → risk → portfolio chain and inspect conviction, horizon votes, and
          final weights.
        </p>
      </header>

      <div className="rounded-2xl border border-line bg-panel p-5 shadow-[0_20px_50px_-30px_rgba(15,28,26,0.35)] backdrop-blur-sm sm:p-6">
        <RunControls
          tickersInput={tickersInput}
          maxPosition={maxPosition}
          loading={loading}
          onTickersChange={setTickersInput}
          onMaxPositionChange={setMaxPosition}
          onRun={handleRun}
        />
        {error ? (
          <p className="mt-4 rounded-lg bg-rose-soft/50 px-3 py-2 font-mono text-sm text-rose">
            {error}
          </p>
        ) : null}
      </div>

      {data ? (
        <>
          <div className="grid gap-6 lg:grid-cols-2">
            <Panel
              title="Conviction"
              subtitle="Blended horizon score per ticker"
              hint={HINTS.conviction}
            >
              <ConvictionChart conviction={data.conviction} />
            </Panel>
            <Panel
              title="Weights"
              subtitle="Final long / short allocation"
              hint={HINTS.weights}
            >
              <WeightsChart weights={data.weights} />
            </Panel>
          </div>

          <Panel
            title="Horizon signals"
            subtitle="Raw −1…+1 votes across holding periods"
            hint={HINTS.horizonSignals}
          >
            <HorizonGrid
              tickers={data.tickers}
              horizons={data.horizons}
              signals={data.signals}
            />
          </Panel>

          <div className="rounded-2xl border border-line bg-panel px-5 py-4 backdrop-blur-sm sm:px-6">
            <MetaStrip
              portfolioVolatility={data.portfolio_volatility}
              targetVolatility={data.target_volatility}
              volatilities={data.volatilities}
            />
          </div>
        </>
      ) : (
        !loading && (
          <p className="text-center text-sm text-muted">
            Hit <span className="font-medium text-ink">Run pipeline</span> to fetch live data and
            size the book.
          </p>
        )
      )}
    </div>
  )
}

function Panel({
  title,
  subtitle,
  hint,
  children,
}: {
  title: string
  subtitle: string
  hint: string
  children: ReactNode
}) {
  return (
    <section className="rounded-2xl border border-line bg-panel p-5 shadow-[0_20px_50px_-30px_rgba(15,28,26,0.25)] backdrop-blur-sm sm:p-6">
      <div className="mb-4">
        <h2 className="text-lg font-semibold tracking-tight">
          <HintLabel label={title} text={hint} />
        </h2>
        <p className="text-sm text-muted">{subtitle}</p>
      </div>
      {children}
    </section>
  )
}
