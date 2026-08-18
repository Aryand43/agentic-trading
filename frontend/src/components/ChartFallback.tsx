/** Placeholder while a lazily-loaded chart chunk is fetched. Height matches the
 *  chart it replaces so the page does not jump when it arrives. */
export function ChartFallback({ className = 'h-64 sm:h-72' }: { className?: string }) {
  return (
    <div
      role="status"
      aria-label="Loading chart"
      className={`w-full animate-pulse rounded-md bg-mist/60 ${className}`}
    />
  )
}
