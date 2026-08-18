import { useCallback, useReducer } from 'react'
import { AgentPanel } from './components/AgentPanel'
import { BacktestPanel } from './components/BacktestPanel'
import { ControlPanel } from './components/ControlPanel'
import { ErrorBoundary } from './components/ErrorBoundary'
import { LivePanel } from './components/LivePanel'
import { useAgent, useBacktest, usePipeline } from './hooks/usePipeline'
import { parseTickers } from './lib/format'
import { DESK_VERSION, formatDeskError } from './lib/errors'
import {
  INITIAL_PARAMS,
  deskReducer,
  windowFields,
  type DeskParams,
} from './state/deskParams'

export default function App() {
  const pipeline = usePipeline()
  const backtest = useBacktest()
  const agent = useAgent()

  const [params, dispatch] = useReducer(deskReducer, INITIAL_PARAMS)

  const onChange = useCallback(
    (patch: Partial<DeskParams>) => dispatch({ type: 'set', patch }),
    [],
  )
  const onApplyPreset = useCallback(
    (years: number) => dispatch({ type: 'applyPreset', years }),
    [],
  )

  const loading = pipeline.loading || backtest.loading || agent.loading

  const handleCancel = useCallback(() => {
    pipeline.cancel()
    backtest.cancel()
    agent.cancel()
  }, [pipeline, backtest, agent])

  // Attribute the failure so a stale banner can never be mistaken for the
  // active mode's result. Errors are also cleared across modes on every run.
  const failure = backtest.error
    ? { mode: 'Backtest', message: backtest.error }
    : pipeline.error
      ? { mode: 'Live', message: pipeline.error }
      : agent.error
        ? { mode: 'Agent', message: agent.error }
        : null
  const errorText = formatDeskError(failure?.message)

  const handleRun = async () => {
    // Any previous mode's failure is stale the moment a new run starts.
    pipeline.clearError()
    backtest.clearError()
    agent.clearError()

    const parsed = parseTickers(params.tickersInput)
    const tickers = parsed.length ? parsed : null

    if (params.mode === 'live') {
      await pipeline.run({
        tickers,
        max_position: params.maxPosition,
        gross_exposure: params.grossExposure,
        target_volatility: params.targetVolatility,
      })
      return
    }

    if (params.mode === 'backtest') {
      const result = await backtest.run({
        tickers,
        ...windowFields(params),
        initial_capital: params.initialCapital,
        max_position: params.maxPosition,
        gross_exposure: params.grossExposure,
        target_volatility: params.targetVolatility,
        include_baselines: params.includeBaselines,
        include_segments: params.includeSegments,
      })
      if (result?.window) dispatch({ type: 'snapToWindow', window: result.window })
      return
    }

    const result = await agent.run({
      tickers,
      ...windowFields(params),
      horizon: params.horizon,
      n_iterations: params.iterations,
      initial_capital: params.initialCapital,
    })
    if (result?.window) dispatch({ type: 'snapToWindow', window: result.window })
  }

  const hasResults = Boolean(backtest.data || agent.data || pipeline.data)

  return (
    <div className="relative isolate mx-auto flex min-h-screen w-full max-w-3xl min-w-0 flex-col gap-8 overflow-x-clip px-4 py-8 sm:max-w-5xl sm:px-6 sm:py-10 lg:max-w-6xl">
      <header className="flex flex-wrap items-end justify-between gap-3 border-b border-line/80 pb-5">
        <div>
          <p className="font-mono text-[11px] uppercase tracking-[0.18em] text-teal">
            Agentic Trading
          </p>
          <h1 className="mt-1 text-2xl font-semibold tracking-tight text-ink sm:text-3xl">
            Research desk
          </h1>
        </div>
        <p className="font-mono text-[11px] text-muted">{DESK_VERSION}</p>
      </header>

      <main className="flex min-w-0 flex-col gap-8">
        <ErrorBoundary name="Run controls">
          <ControlPanel
            params={params}
            onChange={onChange}
            onApplyPreset={onApplyPreset}
            loading={loading}
            onRun={handleRun}
            onCancel={handleCancel}
          />
        </ErrorBoundary>

        {errorText ? (
          <div
            role="alert"
            className="rounded-lg border border-rose/20 bg-rose-soft/40 px-4 py-3 text-sm animate-[fadeIn_0.25s_ease-out]"
          >
            <p className="font-medium text-ink">{failure?.mode} run failed</p>
            <p className="mt-0.5 text-rose/95">{errorText}</p>
          </div>
        ) : null}

        {!hasResults && !loading ? (
          <p className="text-center text-sm text-muted">
            Choose a window, then run a <span className="text-ink">backtest</span>.
          </p>
        ) : null}

        {backtest.data ? (
          <ErrorBoundary name="Backtest results">
            <BacktestPanel data={backtest.data} />
          </ErrorBoundary>
        ) : null}

        {agent.data ? (
          <ErrorBoundary name="Agent results">
            <AgentPanel data={agent.data} />
          </ErrorBoundary>
        ) : null}

        {pipeline.data ? (
          <ErrorBoundary name="Live book">
            <LivePanel
              data={pipeline.data}
              requested={{
                maxPosition: params.maxPosition,
                grossExposure: params.grossExposure,
              }}
            />
          </ErrorBoundary>
        ) : null}
      </main>
    </div>
  )
}
