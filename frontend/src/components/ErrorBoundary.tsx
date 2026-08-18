import { Component, type ErrorInfo, type ReactNode } from 'react'

type Props = {
  /** Shown in the fallback so the reader knows which panel died. */
  name: string
  children: ReactNode
}

type State = { error: Error | null }

/** Contains a render crash to one panel.
 *
 * Panels render backend-shaped data, some of it untyped (`portfolios` is a bare
 * dict narrowed by a cast). Without a boundary a single bad field blanks the
 * whole page and takes every other result with it — including a backtest that
 * took 15 seconds to produce. Scoping the boundary per panel keeps the rest of
 * the desk usable and says plainly what failed.
 */
export class ErrorBoundary extends Component<Props, State> {
  state: State = { error: null }

  static getDerivedStateFromError(error: Error): State {
    return { error }
  }

  componentDidCatch(error: Error, info: ErrorInfo) {
    console.error(`[${this.props.name}] render failed`, error, info.componentStack)
  }

  handleRetry = () => this.setState({ error: null })

  render() {
    const { error } = this.state
    if (!error) return this.props.children

    return (
      <section
        role="alert"
        className="rounded-lg border border-rose/25 bg-rose-soft/30 px-4 py-3 text-sm"
      >
        <p className="font-medium text-ink">{this.props.name} could not be displayed</p>
        <p className="mt-0.5 text-rose/95">
          This panel hit a rendering error. Your other results are unaffected.
        </p>
        <p className="mt-2 font-mono text-[11px] break-words text-muted">{error.message}</p>
        <button
          type="button"
          onClick={this.handleRetry}
          className="mt-3 h-8 rounded-md border border-line bg-white px-3 text-xs font-medium text-muted transition hover:border-teal hover:text-ink"
        >
          Try again
        </button>
      </section>
    )
  }
}
