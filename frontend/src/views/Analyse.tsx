import { useEffect, useRef, useState } from 'react'
import { ArrowRight, CircleHelp, Loader2, MessageSquareText, Sparkles } from 'lucide-react'
import { names, number, request } from '../api'
import type { Analysis, ModelSpec } from '../api'
import { Badge, Empty } from '../components/common'
import { SentenceBreakdown } from '../components/SentenceBreakdown'

type Result = { analysis: Analysis; elapsed_ms: number }
type Props = {
  modelId: string
  models: ModelSpec[]
  text: string
  onTextChange: (value: string) => void
  onModelChange: (value: string) => void
  onModelGuide: () => void
}
const examples = [
  ['Opposing opinions', 'The camera is excellent, but the battery is terrible.'],
  ['Negation', "The camera isn't good, but the screen is excellent."],
  ['General opinion', 'I absolutely love this phone!'],
] as const

function AnalyseView({ modelId, models, text, onTextChange, onModelChange, onModelGuide }: Props) {
  const [results, setResults] = useState<Result[]>([])
  const [submittedText, setSubmittedText] = useState('')
  const [compare, setCompare] = useState(false)
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState('')
  const activeRequest = useRef<AbortController | null>(null)
  const requestNumber = useRef(0)
  const resultHeading = useRef<HTMLDivElement | null>(null)
  const model = models.find((item) => item.id === modelId)
  const primaryModels = models.filter(
    (item) => item.recommended_for_live || item.kind === 'rule_baseline',
  )
  const experimentalModels = models.filter((item) => !primaryModels.includes(item))

  useEffect(() => {
    activeRequest.current?.abort()
    requestNumber.current += 1
    setResults([])
    setSubmittedText('')
    setError('')
    setBusy(false)
    return () => {
      activeRequest.current?.abort()
      requestNumber.current += 1
    }
  }, [modelId])

  useEffect(() => {
    if (results.length) resultHeading.current?.scrollIntoView({ block: 'start' })
  }, [results])

  function edit(value: string) {
    onTextChange(value)
    setResults([])
    setSubmittedText('')
    setError('')
  }

  async function submit() {
    const controller = new AbortController()
    activeRequest.current?.abort()
    activeRequest.current = controller
    const currentRequest = ++requestNumber.current
    const input = text
    setBusy(true)
    setError('')
    setResults([])
    setSubmittedText('')
    try {
      let next: Result[]
      if (compare && modelId !== 'rules-v1') {
        const response = await request<{ results: Result[] }>('/api/analyse/compare', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ text: input, models: [modelId, 'rules-v1'] }),
          signal: controller.signal,
        })
        next = response.results
      } else {
        const started = performance.now()
        const analysis = await request<Analysis>('/api/analyse', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ text: input, model: modelId }),
          signal: controller.signal,
        })
        next = [{ analysis, elapsed_ms: performance.now() - started }]
      }
      if (controller.signal.aborted || currentRequest !== requestNumber.current) return
      setResults(next)
      setSubmittedText(input)
    } catch (error) {
      if (!controller.signal.aborted && currentRequest === requestNumber.current) {
        setError((error as Error).message)
      }
    } finally {
      if (currentRequest === requestNumber.current) setBusy(false)
    }
  }

  return (
    <>
      <section className="panel live-model-bar">
        <div>
          <label htmlFor="live-model">Live-review model</label>
          <select
            id="live-model"
            aria-label="Live-review model"
            value={modelId}
            onChange={(event) => onModelChange(event.target.value)}
          >
            <optgroup label="Live review and baseline">
              {primaryModels.map((item) => (
                <option key={item.id} value={item.id} disabled={!item.available}>
                  {item.name}
                  {!item.available ? ' · setup required' : ''}
                </option>
              ))}
            </optgroup>
            <optgroup label="Research comparisons and earlier versions">
              {experimentalModels.map((item) => (
                <option key={item.id} value={item.id} disabled={!item.available}>
                  {item.name}
                  {!item.available ? ' · setup required' : ''}
                </option>
              ))}
            </optgroup>
          </select>
          <p>
            {!model
              ? 'Loading locally installed models…'
              : model.recommended_for_live
                ? 'Smartphone context finds features. DeBERTa predicts the opinion about each one.'
                : model?.kind === 'rule_baseline'
                  ? 'Rules + VADER is the comparison baseline. It does not use DeBERTa.'
                  : 'Research model. Review its training data and limitations before using its output.'}
          </p>
        </div>
        <button className="text-button" onClick={onModelGuide}>
          Which model does what? <ArrowRight size={15} />
        </button>
      </section>
      {!models.some((item) => item.recommended_for_live && item.available) && models.length > 0 && (
        <div className="alert info">
          The recommended neural model needs local setup. Run <code>make model-setup</code> and
          restart the application. The selected baseline remains identified below.
        </div>
      )}
      <section className="panel input-panel">
        <div className="panel-title">
          <div>
            <h2>Enter any smartphone review</h2>
            <p>Your own text runs through the selected model. No dataset import is needed.</p>
          </div>
          <span className="subtle-chip">ENGLISH</span>
        </div>
        <textarea
          aria-label="Review text"
          placeholder="Type or paste a review. For example: The camera is excellent, but the battery is terrible."
          value={text}
          disabled={busy}
          onChange={(event) => edit(event.target.value)}
          maxLength={30000}
        />
        <div className="input-footer">
          <span>{number(text.length)} / 30,000 characters · local inference</span>
          <button
            className="button primary"
            disabled={!text.trim() || busy || !model?.available}
            onClick={submit}
          >
            {busy ? <Loader2 className="spin" size={16} /> : <Sparkles size={16} />}
            {busy ? 'Analysing…' : 'Analyse review'}
          </button>
        </div>
        <div className="live-input-options">
          {modelId !== 'rules-v1' && (
            <label className="compare-toggle">
              <input
                type="checkbox"
                checked={compare}
                disabled={busy}
                onChange={(event) => {
                  setCompare(event.target.checked)
                  setResults([])
                  setSubmittedText('')
                }}
              />
              Also compare with the Rules + VADER baseline
            </label>
          )}
          <details className="sample-reviews">
            <summary>Sample inputs</summary>
            <div>
              {examples.map(([label, value]) => (
                <button
                  className="text-button"
                  key={label}
                  disabled={busy}
                  onClick={() => edit(value)}
                >
                  {label}
                </button>
              ))}
            </div>
            <p className="small-note">Written examples, outside the research evaluation.</p>
          </details>
        </div>
        {busy && (
          <p className="small-note" role="status">
            Running {model?.name}. The first neural request also loads the checkpoint.
          </p>
        )}
        {error && (
          <div className="inline-error" role="alert">
            {error}
          </div>
        )}
      </section>
      {!!results.length && (
        <div className="live-result-heading" aria-live="polite" ref={resultHeading}>
          <h2>Analysis results</h2>
          <p>
            Read each sentence and its feature opinions below. The review summary combines opinions
            across the full input.
          </p>
        </div>
      )}
      <div className={'model-results ' + (results.length > 1 ? 'side-by-side' : '')}>
        {!results.length ? (
          <section className="panel">
            <Empty title="Ready for your review" icon={<MessageSquareText size={26} />}>
              Enter English text above and select Analyse review.
            </Empty>
          </section>
        ) : (
          results.map(({ analysis, elapsed_ms }) => {
            const usedModel = models.find((item) => item.id === analysis.model_id)
            return (
              <section key={analysis.model_id} className="panel results-panel">
                <div className="panel-title">
                  <div>
                    <h2>{usedModel?.name || analysis.model_id}</h2>
                    <p>
                      {analysis.aspects.length} feature{analysis.aspects.length === 1 ? '' : 's'}
                      {' · '}
                      {analysis.sentences.length} sentence
                      {analysis.sentences.length === 1 ? '' : 's'}
                      {' · '}
                      {Math.round(elapsed_ms)} ms
                      {' · '}
                      {results.length > 1 ? 'inference time' : 'request time, including first load'}
                    </p>
                  </div>
                </div>
                <div className="analysis-result">
                  {!!analysis.aspects.length && (
                    <div className="review-summary">
                      <h3>Review summary</h3>
                      <div className="aspect-summary-list">
                        {analysis.aspects.map((aspect) => (
                          <div className="aspect-summary-item" key={aspect.category}>
                            <span>{names[aspect.category]}</span>
                            <Badge state={aspect.sentiment} />
                          </div>
                        ))}
                      </div>
                      <p>Mixed means this feature has opposing opinions in the review.</p>
                    </div>
                  )}
                  {analysis.general_opinion && (
                    <div className="general-opinion">
                      <div>
                        <h3>General phone opinion</h3>
                        <Badge state={analysis.general_opinion.sentiment} />
                      </div>
                      <p>
                        The review does not identify a specific feature. This opinion is separate
                        from aspect predictions.
                      </p>
                    </div>
                  )}
                  {analysis.supported && <SentenceBreakdown analysis={analysis} />}
                  {!analysis.aspects.length && !analysis.general_opinion && (
                    <Empty
                      title={
                        analysis.supported
                          ? 'No phone feature identified'
                          : 'This language is not supported'
                      }
                    >
                      {analysis.supported
                        ? 'The text may be general, unrelated to phone features or too implicit for this model. No aspect label is invented.'
                        : 'Use an English review for this version.'}
                    </Empty>
                  )}
                </div>
                <details className="analysis-explanation">
                  <summary>How this result was produced</summary>
                  <dl>
                    <div>
                      <dt>Model</dt>
                      <dd>{analysis.model_id}</dd>
                    </div>
                    <div>
                      <dt>Feature detection</dt>
                      <dd>{usedModel?.aspect_method || usedModel?.description}</dd>
                    </div>
                    <div>
                      <dt>Sentiment</dt>
                      <dd>{usedModel?.sentiment_method || usedModel?.family}</dd>
                    </div>
                  </dl>
                  {!!analysis.inference_steps?.length && (
                    <div className="comparison-scroll">
                      <table className="inference-table">
                        <thead>
                          <tr>
                            <th>Feature</th>
                            <th>Feature cue</th>
                            <th>Model context</th>
                            <th>Prediction</th>
                          </tr>
                        </thead>
                        <tbody>
                          {analysis.inference_steps.map((step, index) => (
                            <tr key={index}>
                              <th>{names[step.category]}</th>
                              <td>{step.cue}</td>
                              <td>{step.context}</td>
                              <td>
                                <Badge state={step.sentiment} />
                              </td>
                            </tr>
                          ))}
                        </tbody>
                      </table>
                    </div>
                  )}
                  <p className="small-note">
                    Sentence cards preserve the original input. Opinion quotes show the exact local
                    evidence; the trace records the context passed to the classifier. An omitted
                    feature may be supplied from the previous clause when its reference is
                    unambiguous.
                  </p>
                  <p className="small-note">Input analysed: {submittedText}</p>
                </details>
                <details className="result-warnings live-limitations">
                  <summary>Model limitations</summary>
                  {analysis.warnings.map((warning) => (
                    <p key={warning}>
                      <CircleHelp size={13} />
                      {warning}
                    </p>
                  ))}
                </details>
              </section>
            )
          })
        )}
      </div>
    </>
  )
}
export default AnalyseView
