import { afterEach, describe, expect, it, vi } from 'vitest'
import { CancelledError, isCancelled, runBacktest, TIMEOUTS } from './client'

const realFetch = globalThis.fetch

afterEach(() => {
  globalThis.fetch = realFetch
  vi.restoreAllMocks()
})

/** A fetch that never settles until its signal aborts, like a hung API. */
function hangingFetch() {
  return vi.fn((_url: string, init?: RequestInit) => {
    return new Promise<Response>((_resolve, reject) => {
      const fail = () => {
        const err = new Error('aborted')
        err.name = 'AbortError'
        reject(err)
      }
      // Real fetch rejects straight away for a signal that is already aborted;
      // the event would never fire in that case.
      if (init?.signal?.aborted) return fail()
      init?.signal?.addEventListener('abort', fail)
    })
  })
}

function jsonResponse(body: unknown, status = 200): Response {
  return {
    ok: status >= 200 && status < 300,
    status,
    json: async () => body,
  } as Response
}

describe('timeout', () => {
  it('gives up on a hung request and says how long it waited', async () => {
    globalThis.fetch = hangingFetch() as unknown as typeof fetch

    await expect(runBacktest({}, { timeoutMs: 20 })).rejects.toThrow(
      /did not respond within 0s|did not respond within/,
    )
  })

  it('does not report a timeout as a cancellation', async () => {
    globalThis.fetch = hangingFetch() as unknown as typeof fetch
    try {
      await runBacktest({}, { timeoutMs: 20 })
      expect.unreachable('should have thrown')
    } catch (err) {
      expect(isCancelled(err)).toBe(false)
    }
  })

  it('uses a longer ceiling for the agent than for a live snapshot', () => {
    expect(TIMEOUTS.agent).toBeGreaterThan(TIMEOUTS.backtest)
    expect(TIMEOUTS.backtest).toBeGreaterThan(TIMEOUTS.run)
  })
})

describe('cancellation', () => {
  it('throws CancelledError when the caller aborts', async () => {
    globalThis.fetch = hangingFetch() as unknown as typeof fetch
    const controller = new AbortController()
    const promise = runBacktest({}, { signal: controller.signal, timeoutMs: 60_000 })
    controller.abort()

    await expect(promise).rejects.toBeInstanceOf(CancelledError)
  })

  it('is recognisable via isCancelled so the UI can stay quiet', async () => {
    globalThis.fetch = hangingFetch() as unknown as typeof fetch
    const controller = new AbortController()
    const promise = runBacktest({}, { signal: controller.signal, timeoutMs: 60_000 })
    controller.abort()

    await promise.catch((err) => expect(isCancelled(err)).toBe(true))
  })

  it('aborts an already-cancelled request immediately', async () => {
    globalThis.fetch = hangingFetch() as unknown as typeof fetch
    await expect(
      runBacktest({}, { signal: AbortSignal.abort(), timeoutMs: 60_000 }),
    ).rejects.toBeInstanceOf(CancelledError)
  })
})

describe('error surfacing', () => {
  it('extracts a string detail from an error response', async () => {
    globalThis.fetch = vi.fn(async () =>
      jsonResponse({ detail: 'Unknown horizon: 7d' }, 400),
    ) as unknown as typeof fetch

    await expect(runBacktest({})).rejects.toThrow('Unknown horizon: 7d')
  })

  it('joins FastAPI validation detail arrays', async () => {
    globalThis.fetch = vi.fn(async () =>
      jsonResponse({ detail: [{ msg: 'field required' }, { msg: 'too small' }] }, 422),
    ) as unknown as typeof fetch

    await expect(runBacktest({})).rejects.toThrow('field required; too small')
  })

  it('falls back to the status code when the body is not JSON', async () => {
    globalThis.fetch = vi.fn(async () => ({
      ok: false,
      status: 502,
      json: async () => {
        throw new Error('not json')
      },
    })) as unknown as typeof fetch

    await expect(runBacktest({})).rejects.toThrow('Request failed (502)')
  })

  it('returns the parsed body on success', async () => {
    globalThis.fetch = vi.fn(async () =>
      jsonResponse({ tickers: ['AAPL'] }),
    ) as unknown as typeof fetch

    await expect(runBacktest({})).resolves.toEqual({ tickers: ['AAPL'] })
  })
})
