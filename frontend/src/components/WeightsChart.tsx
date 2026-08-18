import { SignedBarChart } from './SignedBarChart'

type WeightsChartProps = {
  weights: Record<string, number>
}

export function WeightsChart({ weights }: WeightsChartProps) {
  return <SignedBarChart values={weights} label="Weight" minSpan={0.1} yAxisWidth={44} />
}
