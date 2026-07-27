import type { ReactNode } from 'react'

type HintProps = {
  text: string
  children: ReactNode
  className?: string
  side?: 'top' | 'bottom'
}

/** Hover popup that explains a feature. Keeps layout intact via group/relative. */
export function Hint({ text, children, className = '', side = 'top' }: HintProps) {
  const position =
    side === 'top'
      ? 'bottom-[calc(100%+8px)]'
      : 'top-[calc(100%+8px)]'

  const arrow =
    side === 'top'
      ? 'top-full left-1/2 -mt-px -translate-x-1/2 border-4 border-transparent border-t-ink'
      : 'bottom-full left-1/2 -mb-px -translate-x-1/2 border-4 border-transparent border-b-ink'

  return (
    <span className={`group/hint relative inline-flex items-center ${className}`}>
      {children}
      <span
        role="tooltip"
        className={`pointer-events-none absolute ${position} left-1/2 z-50 w-56 -translate-x-1/2 rounded-lg border border-line bg-ink px-3 py-2 text-left text-xs font-normal normal-case tracking-normal text-fog opacity-0 shadow-[0_12px_30px_-12px_rgba(15,28,26,0.55)] transition duration-150 group-hover/hint:opacity-100`}
      >
        {text}
        <span aria-hidden className={`absolute ${arrow}`} />
      </span>
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
  side?: 'top' | 'bottom'
}) {
  return (
    <Hint text={text} className={className} side={side}>
      <span className="cursor-help border-b border-dotted border-muted/50">{label}</span>
    </Hint>
  )
}
