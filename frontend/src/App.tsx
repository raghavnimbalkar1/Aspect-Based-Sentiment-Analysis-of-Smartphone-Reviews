import { lazy, Suspense, useEffect, useState } from 'react'
import {
  ArrowDownToLine,
  ArrowRight,
  ArrowUpRight,
  BarChart3,
  ChevronDown,
  ChevronRight,
  CircleHelp,
  Database,
  FileText,
  ClipboardCheck,
  FlaskConical,
  GitCompareArrows,
  Layers3,
  Loader2,
  MessageSquareText,
  Monitor,
  Plus,
  Search,
  SlidersHorizontal,
  Smartphone,
  Upload,
  X,
} from 'lucide-react'
import { readStored, writeStored } from './storage'
import {
  phoneName,
  colors,
  dateRange,
  emptyFilters,
  names,
  number,
  query,
  request,
  states,
} from './api'
import type { Dataset, FilterValues, Job, Overview, Product, ModelSpec } from './api'
import { useRemote } from './hooks/useRemote'
import { Empty, Legend, Metric } from './components/common'
import ImportDialog from './components/ImportDialog'
import DatasetDetails from './components/DatasetDetails'
import ReviewsView from './components/Reviews'
import AnalyseView from './views/Analyse'
import CompareView from './views/Compare'
import EvaluationView from './views/Evaluation'
import AnnotationView from './views/Annotation'
import ModelsView from './views/Models'
import JobFeedback from './components/JobFeedback'

const SentimentChart = lazy(() => import('./components/SentimentChart'))

type View = 'overview' | 'analyse' | 'reviews' | 'compare' | 'evaluation' | 'annotation' | 'models'
const nav = [
  { id: 'overview', label: 'Overview', icon: BarChart3 },
  { id: 'analyse', label: 'Analyse a review', icon: MessageSquareText },
  { id: 'reviews', label: 'Review explorer', icon: FileText },
  { id: 'compare', label: 'Compare phones', icon: GitCompareArrows },
  { id: 'models', label: 'Models explained', icon: CircleHelp },
  { id: 'annotation', label: 'Annotation', icon: ClipboardCheck },
  { id: 'evaluation', label: 'Model evaluation', icon: FlaskConical },
] as const

function App() {
  const [view, setView] = useState<View>('analyse')
  const [annotationDirty, setAnnotationDirty] = useState(false)
  const [revision, refresh] = useState(0)
  const [modelId, setModelId] = useState('rules-v1')
  const [liveModelId, setLiveModelId] = useState('')
  const [liveText, setLiveText] = useState(() => readStored('aspect.liveDraft', 'session') || '')
  const models = useRemote<ModelSpec[]>('/api/models', revision)
  const [datasetId, setDatasetId] = useState(() => readStored('aspect.dataset') || '')
  const [pendingDatasetId, setPendingDatasetId] = useState('')
  const [filters, setFilters] = useState<FilterValues>(emptyFilters)
  const [search, setSearch] = useState('')
  const [showImport, setShowImport] = useState(false)
  const [message, setMessage] = useState('')
  const [messageKind, setMessageKind] = useState('info')
  const [busy, setBusy] = useState(false)
  const datasets = useRemote<Dataset[]>(`/api/datasets?model=${modelId}`, revision)
  const selected = datasets.data?.find((dataset) => dataset.id === datasetId)
  const base = selected ? `/api/datasets/${selected.id}` : null
  const products = useRemote<Product[]>(base ? `${base}/products` : null)
  const overview = useRemote<Overview>(
    base ? `${base}/overview?${query(filters, modelId)}` : null,
    revision,
  )
  const datasetOverview = useRemote<Overview>(
    base ? `${base}/overview?model=${modelId}` : null,
    revision,
  )
  const jobs = useRemote<Job[]>(base ? `${base}/jobs?model=${modelId}` : null, revision)
  const activeJob = jobs.data?.find((job) => ['queued', 'running'].includes(job.status))

  useEffect(() => {
    window.scrollTo(0, 0)
  }, [view, datasetId])

  useEffect(() => {
    writeStored('aspect.liveDraft', liveText, 'session')
  }, [liveText])

  useEffect(() => {
    if (liveModelId || !models.data?.length) return
    const recommended = models.data.find((model) => model.recommended_for_live && model.available)
    setLiveModelId(recommended?.id || 'rules-v1')
  }, [models.data, liveModelId])

  useEffect(() => {
    if (pendingDatasetId) {
      if (datasets.data?.some((dataset) => dataset.id === pendingDatasetId)) {
        setDatasetId(pendingDatasetId)
        setPendingDatasetId('')
      }
      return
    }
    if (datasets.data?.length && !datasets.data.some((dataset) => dataset.id === datasetId)) {
      setDatasetId(datasets.data[0].id)
    }
  }, [datasets.data, datasetId, pendingDatasetId])
  useEffect(() => {
    writeStored('aspect.dataset', datasetId)
    setFilters(emptyFilters)
    setSearch('')
  }, [datasetId])
  useEffect(() => {
    const timer = window.setTimeout(() => setFilters((current) => ({ ...current, q: search })), 250)
    return () => clearTimeout(timer)
  }, [search])
  useEffect(() => {
    if (!activeJob) return
    const timer = window.setInterval(() => refresh((value) => value + 1), 1500)
    return () => clearInterval(timer)
  }, [activeJob?.id])

  async function startAnalysis() {
    if (!base) return
    setBusy(true)
    setMessage('')
    try {
      await request(`${base}/jobs`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ model: modelId }),
      })
      refresh((value) => value + 1)
    } catch (error) {
      setMessageKind('error')
      setMessage((error as Error).message)
    } finally {
      setBusy(false)
    }
  }

  const heading = {
    overview: ['Review intelligence', 'Understand the details behind every opinion.'],
    analyse: [
      'Analyse a review',
      'See which phone features are discussed and how they are described.',
    ],
    reviews: [
      'Review explorer',
      'Explore original reviews and inspect the sentences behind each prediction.',
    ],
    compare: [
      'Compare phones',
      'Compare feature sentiment across phones, with the sample sizes in view.',
    ],
    annotation: [
      'Annotation workbench',
      'Review sentence labels with their human or AI-assisted origin recorded.',
    ],
    evaluation: [
      'Model evaluation',
      'Track the models, their evaluation, and the work still ahead.',
    ],
    models: [
      'Models explained',
      'Which method runs where, which data it uses, and what we implemented.',
    ],
  }[view]
  const summary = overview.data

  return (
    <div className="app-shell">
      <aside className="sidebar">
        <a
          href="#"
          className="brand"
          onClick={(event) => {
            event.preventDefault()
            if (!annotationDirty) setView('overview')
          }}
        >
          <span className="brand-symbol">
            <Layers3 size={23} />
          </span>
          aspect<span className="brand-period">.</span>
        </a>
        <div className="workspace-label">RESEARCH WORKSPACE</div>
        <nav aria-label="Main navigation">
          {nav.map((item) => (
            <button
              key={item.id}
              disabled={annotationDirty && item.id !== view}
              aria-label={item.label}
              title={item.label}
              onClick={() => {
                setView(item.id)
                setMessage('')
              }}
              className={`nav-link ${view === item.id ? 'active' : ''}`}
            >
              <item.icon size={18} strokeWidth={1.7} />
              <span>{item.label}</span>
              {view === item.id && <i />}
            </button>
          ))}
        </nav>
        <div className="sidebar-section">YOUR DATA</div>
        <button
          className="dataset-link"
          aria-label="Import dataset"
          title="Import dataset"
          onClick={() => setShowImport(true)}
          disabled={annotationDirty}
        >
          <Database size={17} />
          <span>Datasets</span>
          <span className="count">{datasets.data?.length ?? 0}</span>
        </button>
        <div className="sidebar-note">
          <span className="small-overline">BUILT FOR THE DETAILS</span>
          <p>
            One review.
            <br />
            Many perspectives.
          </p>
          <div className="note-lines">
            <i />
            <i />
            <i />
            <i />
            <i />
          </div>
        </div>
        <div className="sidebar-bottom">
          <span className="local-dot" />
          <div>
            Local workspace<small>English · on your device</small>
          </div>
          <Monitor size={16} />
        </div>
      </aside>
      <div className="main-shell">
        <header className="topbar">
          <div className="breadcrumb">
            WORKSPACE <span>/</span> SMARTPHONE REVIEWS
          </div>
          <div className="topbar-actions">
            <label
              className="model-selector"
              hidden={['annotation', 'analyse', 'models', 'evaluation'].includes(view)}
            >
              <span>MODEL</span>
              <select
                aria-label="Analysis model"
                value={modelId}
                onChange={(event) => setModelId(event.target.value)}
              >
                {models.data?.map((model) => (
                  <option key={model.id} value={model.id} disabled={!model.available}>
                    {model.name}
                    {!model.available ? ' · setup required' : ''}
                  </option>
                ))}
              </select>
            </label>
            <span className="local-pill">
              <i />
              Local
            </span>
            <span className="avatar" aria-label="Research workspace">
              RN
            </span>
          </div>
        </header>
        <main>
          <div className="page-heading">
            <div>
              <div className="eyebrow">
                <span />
                ASPECT-BASED SENTIMENT ANALYSIS
              </div>
              <h1>{heading[0]}</h1>
              <p>{heading[1]}</p>
            </div>
            <div className="heading-actions">
              <button
                className="button secondary"
                disabled={annotationDirty}
                onClick={() => setShowImport(true)}
              >
                <Plus size={16} />
                Import reviews
              </button>
              {base && ['overview', 'reviews'].includes(view) && (
                <a className="button primary" href={`${base}/export?${query(filters, modelId)}`}>
                  <ArrowDownToLine size={15} />
                  Export results
                </a>
              )}
            </div>
          </div>
          {(datasets.error || message) && (
            <div role="alert" className={`alert ${datasets.error ? 'error' : messageKind}`}>
              {message || datasets.error}
              <button aria-label="Dismiss" onClick={() => setMessage('')}>
                <X size={16} />
              </button>
            </div>
          )}
          {selected && ['overview', 'reviews', 'compare'].includes(view) && (
            <div className="dataset-bar">
              <div className="dataset-control">
                <Database size={16} />
                <select
                  aria-label="Active dataset"
                  value={datasetId}
                  onChange={(event) => setDatasetId(event.target.value)}
                >
                  {datasets.data?.map((dataset) => (
                    <option key={dataset.id} value={dataset.id}>
                      {dataset.name}
                    </option>
                  ))}
                </select>
                <ChevronDown size={14} />
              </div>
              <div className="dataset-meta">
                <span>{number(selected.accepted)} reviews</span>
                <i />
                <span>
                  {dateRange(
                    datasetOverview.data?.date_from ?? null,
                    datasetOverview.data?.date_to ?? null,
                  )}
                </span>
                <span className="model-tag">
                  {models.data?.find((model) => model.id === modelId)?.kind === 'rule_baseline'
                    ? 'RULE BASELINE'
                    : 'LOCAL MODEL'}
                </span>
              </div>
            </div>
          )}
          {base && ['overview', 'reviews'].includes(view) && (
            <DatasetDetails key={base} base={base} />
          )}
          {base && ['overview', 'reviews', 'compare'].includes(view) && (
            <JobFeedback
              key={`${base}-${modelId}`}
              base={base}
              job={activeJob || jobs.data?.[0]}
              busy={busy}
              onRetry={startAnalysis}
              onChanged={() => refresh((value) => value + 1)}
            />
          )}
          {selected &&
            ['overview', 'reviews', 'compare'].includes(view) &&
            selected.analysed < selected.accepted &&
            !activeJob &&
            !['failed', 'interrupted'].includes(jobs.data?.[0]?.status || '') && (
              <div className="alert info">
                <Database size={17} />
                <span>
                  {number(selected.accepted - selected.analysed)} reviews are ready for analysis
                  with the selected model.{' '}
                  {['transferred_absa', 'domain_absa'].includes(
                    models.data?.find((model) => model.id === modelId)?.kind || '',
                  ) && 'A large neural batch can take several minutes on CPU.'}
                </span>
                <button onClick={startAnalysis} disabled={busy}>
                  {busy ? 'Starting…' : 'Run analysis'}
                  <ArrowRight size={15} />
                </button>
              </div>
            )}
          {view === 'analyse' ? (
            <AnalyseView
              modelId={liveModelId}
              models={models.data || []}
              text={liveText}
              onTextChange={setLiveText}
              onModelChange={setLiveModelId}
              onModelGuide={() => setView('models')}
            />
          ) : view === 'models' ? (
            <ModelsView models={models.data || []} onAnalyse={() => setView('analyse')} />
          ) : view === 'annotation' ? (
            <AnnotationView onDirtyChange={setAnnotationDirty} />
          ) : view === 'evaluation' ? (
            <EvaluationView onModelsChanged={() => refresh((value) => value + 1)} />
          ) : !selected ? (
            <section className="panel">
              <Empty
                title={
                  datasets.loading
                    ? 'Opening your workspace…'
                    : 'Start with a collection of reviews'
                }
              >
                Import a CSV with review text and an optional phone-model column. Your data and
                results will be saved locally.
              </Empty>
              <div className="empty-action">
                <button className="button primary" onClick={() => setShowImport(true)}>
                  <Upload size={16} />
                  Import your first dataset
                </button>
              </div>
            </section>
          ) : (
            <>
              {view !== 'compare' && (
                <div className="filter-bar">
                  <SlidersHorizontal size={16} />
                  <select
                    aria-label="Filter by phone"
                    value={filters.product}
                    onChange={(event) => setFilters({ ...filters, product: event.target.value })}
                  >
                    <option value="">All phone models</option>
                    {products.data?.map((product) => (
                      <option key={product.id} value={product.id}>
                        {phoneName(product.name, product.brand)}
                      </option>
                    ))}
                  </select>
                  <select
                    aria-label="Filter by aspect"
                    value={filters.category}
                    onChange={(event) => setFilters({ ...filters, category: event.target.value })}
                  >
                    <option value="">All aspects</option>
                    {Object.entries(names).map(([id, name]) => (
                      <option key={id} value={id}>
                        {name}
                      </option>
                    ))}
                  </select>
                  <select
                    aria-label="Filter by sentiment"
                    value={filters.sentiment}
                    onChange={(event) => setFilters({ ...filters, sentiment: event.target.value })}
                  >
                    <option value="">All sentiments</option>
                    {states.map((state) => (
                      <option key={state} value={state}>
                        {state[0].toUpperCase() + state.slice(1)}
                      </option>
                    ))}
                  </select>
                  <label className="search-field">
                    <Search size={16} />
                    <input
                      aria-label="Search review text"
                      placeholder="Search reviews…"
                      maxLength={200}
                      value={search}
                      onChange={(event) => setSearch(event.target.value)}
                    />
                  </label>
                  {Object.values(filters).some(Boolean) && (
                    <button
                      className="clear-filters"
                      onClick={() => {
                        setFilters(emptyFilters)
                        setSearch('')
                      }}
                    >
                      Reset
                    </button>
                  )}
                </div>
              )}
              {overview.error && (
                <div className="alert error" role="alert">
                  {overview.error}
                </div>
              )}
              {overview.loading && (
                <div className="refreshing" role="status">
                  <Loader2 className="spin" size={13} />
                  Updating the selected reviews…
                </div>
              )}
              {view === 'overview' && summary && (
                <>
                  <div className="metric-grid">
                    <Metric
                      label="Reviews in view"
                      value={number(summary.reviews)}
                      detail={`${number(summary.analysed)} analysed`}
                      icon={<MessageSquareText size={18} />}
                    />
                    <Metric
                      label="Phone models"
                      value={number(summary.products)}
                      detail="Across the selected reviews"
                      icon={<Smartphone size={18} />}
                    />
                    <Metric
                      label="Aspect mentions"
                      value={number(
                        summary.aspects.reduce((sum, aspect) => sum + aspect.mentions, 0),
                      )}
                      detail="One result per review & aspect"
                      icon={<Layers3 size={18} />}
                    />
                    <Metric
                      label="Positive mentions"
                      value={
                        Object.values(summary.sentiment_totals).some(Boolean)
                          ? `${Math.round((100 * summary.sentiment_totals.positive) / Object.values(summary.sentiment_totals).reduce((a, b) => a + b, 0))}%`
                          : '—'
                      }
                      detail="Share of feature mentions"
                      icon={<BarChart3 size={18} />}
                      accent
                    />
                  </div>
                  <div className="chart-grid">
                    <section className="panel aspect-panel">
                      <div className="panel-title">
                        <div>
                          <h2>The feature-level picture</h2>
                          <p>How people feel about each part of their phone.</p>
                        </div>
                        <span className="subtle-chip">10 aspects</span>
                      </div>
                      <Legend />
                      <div className="aspect-bars">
                        {summary.aspects.map((aspect) => (
                          <button
                            className="aspect-row"
                            key={aspect.category}
                            onClick={() => {
                              setFilters({ ...filters, category: aspect.category })
                              setView('reviews')
                            }}
                            aria-label={`Explore ${aspect.name} reviews`}
                          >
                            <span className="aspect-name">{aspect.name}</span>
                            <span className="stacked-bar">
                              {states.map((state) => (
                                <span
                                  key={state}
                                  style={{
                                    width: `${aspect.mentions ? (100 * aspect[state]) / aspect.mentions : 0}%`,
                                    background: colors[state],
                                  }}
                                  title={`${state}: ${number(aspect[state])}`}
                                />
                              ))}
                            </span>
                            <span className="aspect-count">{number(aspect.mentions)}</span>
                            <ChevronRight size={13} />
                          </button>
                        ))}
                      </div>
                      <div className="panel-footnote">
                        <CircleHelp size={13} />
                        Select an aspect to inspect the original reviews. Bar lengths show sentiment
                        share.
                      </div>
                    </section>
                    <section className="panel sentiment-panel">
                      <div className="panel-title">
                        <div>
                          <h2>Sentiment mix</h2>
                          <p>Across all feature mentions.</p>
                        </div>
                      </div>
                      <Suspense fallback={<div className="loading-line">Loading chart…</div>}>
                        <SentimentChart totals={summary.sentiment_totals} />
                      </Suspense>
                      <div className="sentiment-key">
                        {states.map((state) => (
                          <div key={state}>
                            <span>
                              <i style={{ background: colors[state] }} />
                              {state}
                            </span>
                            <strong>{number(summary.sentiment_totals[state])}</strong>
                          </div>
                        ))}
                      </div>
                      <div className="quiet-note">
                        An overall rating can hide opposing opinions about different features.
                      </div>
                    </section>
                  </div>
                  <section className="panel">
                    <div className="panel-title">
                      <div>
                        <h2>From opinion to evidence</h2>
                        <p>A few reviews from your current selection.</p>
                      </div>
                      <button className="text-button" onClick={() => setView('reviews')}>
                        Explore all reviews
                        <ArrowUpRight size={15} />
                      </button>
                    </div>
                    <ReviewsView
                      base={base!}
                      filters={filters}
                      revision={revision}
                      modelId={modelId}
                      compact
                    />
                  </section>
                  <div className="method-note">
                    <FlaskConical size={16} />
                    <span>
                      Research preview · Results use the selected model. Inspect supporting
                      sentences; implicit references and complex opinions may be missed.
                    </span>
                    <button onClick={() => setView('evaluation')}>
                      View methodology
                      <ArrowRight size={13} />
                    </button>
                  </div>
                </>
              )}
              {view === 'reviews' && (
                <section className="panel">
                  <div className="panel-title">
                    <div>
                      <h2>Original words, visible evidence</h2>
                      <p>
                        Expand a review to inspect all detected aspects and supporting sentences.
                      </p>
                    </div>
                    <span className="subtle-chip">{number(summary?.reviews ?? 0)} reviews</span>
                  </div>
                  <ReviewsView
                    base={base!}
                    filters={filters}
                    revision={revision}
                    modelId={modelId}
                  />
                </section>
              )}
              {view === 'compare' && (
                <CompareView
                  base={base!}
                  products={products.data || []}
                  revision={revision}
                  modelId={modelId}
                />
              )}
            </>
          )}
          <footer className="page-footer">
            <span>
              Aspect<span className="footer-dot">.</span> Smartphone review analysis
            </span>
            <span>Local data. Traceable evidence.</span>
          </footer>
        </main>
      </div>
      {showImport && (
        <ImportDialog
          onClose={() => setShowImport(false)}
          onComplete={(id, result) => {
            setPendingDatasetId(id)
            refresh((value) => value + 1)
            setMessage(result)
            setMessageKind('info')
            setShowImport(false)
          }}
        />
      )}
    </div>
  )
}

export default App
