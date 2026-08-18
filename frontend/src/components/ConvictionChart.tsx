import { SignedBarChart } from './SignedBarChart'

type ConvictionChartProps = {
  conviction: Record<string, number>
}

/** Conviction is bounded [-1, 1], but real values cluster near zero, so the axis
 *  zooms to the data rather than always showing the full theoretical range. */
export function ConvictionChart({ conviction }: ConvictionChartProps) {
  return (
    <SignedBarChart values={conviction} label="Conviction" minSpan={0.25} yAxisWidth={40} />
  )
}
