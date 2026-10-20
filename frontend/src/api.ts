export type Sentiment = 'positive' | 'negative' | 'neutral' | 'mixed'
export type Dataset = {
  id: string
  name: string
  source: string
  accepted: number
  rejected: number
  analysed: number
}
export type Product = {
  id: string
  name: string
  brand: string
  condition: string
  reviews: number
}
export type Evidence = {
  text: string
  start: number
  end: number
  sentiment: Sentiment
  score: number | null
}
export type Aspect = { category: string; sentiment: Sentiment; evidence: Evidence[] }
export type Analysis = {
  model_id: string
  aspects: Aspect[]
  warnings: string[]
  language: string
  supported: boolean
}
export type AspectStats = {
  category: string
  name: string
  positive: number
  negative: number
  neutral: number
  mixed: number
  mentions: number
  net_sentiment: number | null
  mention_rate: number
  limited_evidence: boolean
}
export type Overview = {
  reviews: number
  analysed: number
  supported: number
  pending: number
  unsupported: number
  products: number
  date_from: string | null
  date_to: string | null
  aspects: AspectStats[]
  sentiment_totals: Record<Sentiment, number>
  languages: { language: string; count: number }[]
}
export type Review = {
  id: string
  text: string
  title: string
  product_name: string
  brand: string
  date: string | null
  rating: number | null
  language: string
  analysis: Analysis | null
}
export type ReviewPage = { total: number; page: number; page_size: number; items: Review[] }
export type Job = {
  id: string
  status: string
  total: number
  processed: number
  failed: number
  error: string | null
}
export type ModelSpec = {
  id: string
  name: string
  kind?: string
  available: boolean
  description: string
  device?: string
  setup?: string
  development_tuned?: boolean
}
export type TaskSet = {
  id: string
  name: string
  total: number
  completed: number
  drafts: number
  pilot_train_only: boolean
  partitions: Record<
    string,
    { total: number; completed: number; completed_human: number; completed_assisted: number }
  >
}
export type MetricScore = {
  precision: number
  recall: number
  f1: number
  true_positive: number
  false_positive: number
  false_negative: number
}
export type ModelMetrics = {
  tuple_micro: MetricScore
  presence_micro: MetricScore
  tuple_macro_f1: number
  per_category: Record<string, MetricScore & { gold_support: number; predicted_support: number }>
  confusion_matrix: Record<string, Record<string, number>>
  sentences: number
  pairs: number
}
export type ExperimentReport = {
  experiment: string
  model_id: string
  training_sentences: number
  validation: Record<string, ModelMetrics>
  test?: Record<string, ModelMetrics>
  test_evaluated: boolean
  elapsed_seconds: number
  annotations_sha256: string
  manifest_sha256: string
  warnings?: string[]
  development?: {
    reference_previously_inspected: boolean
    protocol_sha256: string
    trial: number
  }
  prediction_artifact?: { rows: number; sha256: string }
  evaluation_reference?: Record<
    string,
    { kind: string; independent: boolean; human_only_sentences: number; assisted_sentences: number }
  >
  evaluation_coverage?: Record<
    string,
    {
      expected_sentences: number | null
      labelled_sentences: number
      complete: boolean
    }
  >
}
export type ExperimentRun = {
  id: string
  study_name: string
  set_id: string
  kind: 'compare' | 'train_tfidf'
  status: string
  created_at: string
  error: string | null
  config: { experiment: string; models: string[]; completed_sentences: Record<string, number> }
}
export type Evaluation = {
  active_model: string
  models: (ModelSpec & { status: string })[]
  reports: ExperimentReport[]
  report_errors?: { experiment: string; error: string }[]
}
export type FilterValues = { product: string; category: string; sentiment: string; q: string }
export const emptyFilters: FilterValues = { product: '', category: '', sentiment: '', q: '' }
export const names: Record<string, string> = {
  battery: 'Battery',
  charging: 'Charging',
  camera: 'Camera',
  display: 'Display',
  performance: 'Performance & thermals',
  software: 'Software',
  build: 'Build & design',
  audio: 'Audio',
  connectivity: 'Connectivity',
  value: 'Value',
}
export const states: Sentiment[] = ['positive', 'negative', 'neutral', 'mixed']
export const colors: Record<Sentiment, string> = {
  positive: '#4f8d76',
  negative: '#cf8576',
  neutral: '#c4cbd2',
  mixed: '#c2a569',
}

export async function request<T>(url: string, init?: RequestInit): Promise<T> {
  const response = await fetch(url, init)
  if (!response.ok) {
    const payload = await response.json().catch(() => ({}))
    const detail = payload.detail
    throw new Error(
      typeof detail === 'string'
        ? detail
        : Array.isArray(detail)
          ? detail.map((item: { msg: string }) => item.msg).join('; ')
          : `Request failed (${response.status})`,
    )
  }
  return response.json()
}

export function query(filters: FilterValues, model = 'rules-v1'): string {
  return new URLSearchParams([
    ...Object.entries(filters).filter(([, value]) => value !== ''),
    ['model', model],
  ]).toString()
}

export function number(value: number): string {
  return new Intl.NumberFormat('en-IN').format(value)
}
export function dateRange(from: string | null, to: string | null): string {
  const format = (value: string) =>
    new Date(`${value}T12:00:00`).toLocaleDateString('en-GB', { month: 'short', year: 'numeric' })
  return from && to ? `${format(from)} – ${format(to)}` : 'Date coverage unavailable'
}
