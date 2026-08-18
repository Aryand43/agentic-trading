import {
  useCallback,
  useEffect,
  useId,
  useRef,
  useState,
  type CSSProperties,
  type ReactNode,
} from 'react'
import { createPortal } from 'react-dom'

type Side = 'top' | 'bottom'

type HintProps = {
  text: string
  children: ReactNode
  className?: string
  side?: Side
}

const GAP = 8
/** Keep the bubble this far from the viewport edge. */
const MARGIN = 8
/** Matches the w-56 bubble width. */
const WIDTH = 224
/** Room needed on a side before we commit to it; short hints never exceed this. */
const CLEARANCE = 120

type Placement = {
  left: number
  /** Distance from the viewport top, when opening downward. */
  top?: number
  /** Distance from the viewport bottom, when opening upward. Using `bottom`
   *  anchors to the top edge of the trigger without needing the bubble height. */
  bottom?: number
  side: Side
  /** Arrow offset within the bubble, so it still points at the trigger after clamping. */
  arrowLeft: number
  width: number
}

/** Hover/focus popup that explains a feature.
 *
 * The bubble renders in a portal with `position: fixed`, for two reasons:
 *
 *  1. Escaping clipping. Any `overflow-x-auto` ancestor (every scrollable table
 *     here) computes `overflow-y` to `auto` as well, which cropped bubbles that
 *     opened upward from a table header.
 *  2. Escaping layout. A bubble that is never in the document flow cannot widen
 *     the page, which used to cause sideways scroll on narrow viewports.
 *
 * Position is clamped to the viewport and flips side when there is no room.
 */
export function Hint({ text, children, className = '', side = 'top' }: HintProps) {
  const anchorRef = useRef<HTMLSpanElement>(null)
  const [placement, setPlacement] = useState<Placement | null>(null)
  const id = useId()

  const place = useCallback(() => {
    const el = anchorRef.current
    if (!el) return
    const r = el.getBoundingClientRect()
    const vw = document.documentElement.clientWidth
    const vh = document.documentElement.clientHeight

    const width = Math.min(WIDTH, vw - MARGIN * 2)
    const centre = r.left + r.width / 2
    const left = Math.max(MARGIN, Math.min(centre - width / 2, vw - width - MARGIN))

    // Flip when the preferred side has no room.
    let resolved: Side = side
    if (side === 'top' && r.top < CLEARANCE) resolved = 'bottom'
    if (side === 'bottom' && vh - r.bottom < CLEARANCE) resolved = 'top'

    setPlacement({
      left,
      ...(resolved === 'top' ? { bottom: vh - r.top + GAP } : { top: r.bottom + GAP }),
      side: resolved,
      arrowLeft: Math.max(12, Math.min(centre - left, width - 12)),
      width,
    })
  }, [side])

  const close = useCallback(() => setPlacement(null), [])

  useEffect(() => {
    if (!placement) return
    const onKey = (e: KeyboardEvent) => {
      if (e.key === 'Escape') close()
    }
    // Recompute rather than drift when the page moves underneath the bubble.
    window.addEventListener('scroll', place, true)
    window.addEventListener('resize', place)
    window.addEventListener('keydown', onKey)
    return () => {
      window.removeEventListener('scroll', place, true)
      window.removeEventListener('resize', place)
      window.removeEventListener('keydown', onKey)
    }
  }, [placement, place, close])

  const style: CSSProperties | undefined = placement
    ? {
        left: placement.left,
        top: placement.top,
        bottom: placement.bottom,
        width: placement.width,
      }
    : undefined

  return (
    <span
      ref={anchorRef}
      className={`relative inline-block max-w-full align-baseline ${className}`}
      onMouseEnter={place}
      onMouseLeave={close}
      onFocus={place}
      onBlur={close}
      aria-describedby={placement ? id : undefined}
    >
      {children}
      {placement
        ? createPortal(
            <span
              id={id}
              role="tooltip"
              style={style}
              className="pointer-events-none fixed z-50 block rounded-lg border border-line bg-ink px-3 py-2 text-left text-xs font-normal normal-case tracking-normal text-fog shadow-[0_12px_30px_-12px_rgba(15,28,26,0.55)] animate-[fadeIn_0.12s_ease-out]"
            >
              {text}
              <span
                aria-hidden
                style={{ left: placement.arrowLeft }}
                className={
                  placement.side === 'top'
                    ? 'absolute top-full -mt-px -translate-x-1/2 border-4 border-transparent border-t-ink'
                    : 'absolute bottom-full -mb-px -translate-x-1/2 border-4 border-transparent border-b-ink'
                }
              />
            </span>,
            document.body,
          )
        : null}
    </span>
  )
}

export function HintLabel({
  label,
  text,
  className = '',
  side = 'top',
}: {
  label: string
  text: string
  className?: string
  side?: Side
}) {
  return (
    <Hint text={text} className={className} side={side}>
      <span tabIndex={0} className="cursor-help border-b border-dotted border-muted/50">
        {label}
      </span>
    </Hint>
  )
}
