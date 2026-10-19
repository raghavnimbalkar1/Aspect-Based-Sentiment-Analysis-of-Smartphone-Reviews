import { useState } from 'react'
import { ArrowUpRight, CircleHelp, Loader2, MessageSquareText, Sparkles } from 'lucide-react'
import { names, number, request } from '../api'
import type { Analysis, ModelSpec } from '../api'
import { Badge, Empty } from '../components/common'

type Result = { analysis: Analysis; elapsed_ms: number }

function AnalyseView({ modelId, models }: { modelId: string; models: ModelSpec[] }) {
  const [text, setText] = useState('')
  const [results, setResults] = useState<Result[]>([])
  const [compare, setCompare] = useState(false)
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState('')
  const model = models.find((item) => item.id === modelId)
  async function submit() {
    setBusy(true)
    setError('')
    setResults([])
    try {
      if (compare && modelId !== 'rules-v1') {
        const result = await request<{ results: Result[] }>('/api/analyse/compare', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ text, models: ['rules-v1', modelId] }),
        })
        setResults(result.results)
      } else {
        const started = performance.now()
        const analysis = await request<Analysis>('/api/analyse', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ text, model: modelId }),
        })
        setResults([{ analysis, elapsed_ms: performance.now() - started }])
      }
    } catch (error) {
      setError((error as Error).message)
    } finally {
      setBusy(false)
    }
  }
  return (
    <>
      <section className="panel input-panel">
        <div className="panel-title">
          <div>
            <h2>The review</h2>
            <p>Keep the original wording, including contrasting opinions.</p>
          </div>
          <span className="subtle-chip">ENGLISH</span>
        </div>
        <textarea
          aria-label="Review text"
          placeholder="The camera takes sharp photos, but the battery barely lasts until lunch…"
          value={text}
          disabled={busy}
          onChange={(event) => {
            setText(event.target.value)
            setResults([])
          }}
          maxLength={30000}
        />
        <div className="input-footer">
          <span>
            {number(text.length)} / 30,000 characters · {model?.name || modelId}
          </span>
          <button className="button primary" disabled={!text.trim() || busy} onClick={submit}>
            {busy ? <Loader2 className="spin" size={16} /> : <Sparkles size={16} />}
            {busy ? 'Analysing…' : 'Analyse review'}
          </button>
        </div>
        {modelId !== 'rules-v1' && (
          <label className="compare-toggle">
            <input
              type="checkbox"
              checked={compare}
              disabled={busy}
              onChange={(event) => {
                setCompare(event.target.checked)
                setResults([])
              }}
            />
            Compare with Rules + VADER on the same review
          </label>
        )}
        <button
          className="text-button example-link"
          disabled={busy}
          onClick={() => {
            setText(
              'The camera takes sharp photos, but the battery barely lasts until lunch. The screen is bright and the phone gets hot while gaming.',
            )
            setResults([])
          }}
        >
          Try a demonstration example
          <ArrowUpRight size={14} />
        </button>
        <p className="small-note">
          Illustrative example, outside the evaluation set. The neural model may take a few seconds
          on first use.
        </p>
        {error && (
          <div className="inline-error" role="alert">
            {error}
          </div>
        )}
      </section>
      <div className={`model-results ${results.length > 1 ? 'side-by-side' : ''}`}>
        {!results.length ? (
          <section className="panel">
            <Empty title="The details will appear here" icon={<MessageSquareText size={26} />}>
              Add a review and select Analyse review.
            </Empty>
          </section>
        ) : (
          results.map(({ analysis, elapsed_ms }) => (
            <section key={analysis.model_id} className="panel results-panel">
              <div className="panel-title">
                <div>
                  <h2>
                    {models.find((item) => item.id === analysis.model_id)?.name ||
                      analysis.model_id}
                  </h2>
                  <p>
                    {Math.round(elapsed_ms)} ms ·{' '}
                    {results.length > 1 ? 'inference time' : 'request time, including first load'}
                  </p>
                </div>
              </div>
              <div className="analysis-result">
                {analysis.aspects.map((aspect) => (
                  <div className="single-aspect" key={aspect.category}>
                    <div>
                      <h3>{names[aspect.category]}</h3>
                      <Badge state={aspect.sentiment} />
                    </div>
                    {aspect.evidence.map((evidence, index) => (
                      <blockquote key={index}>{evidence.text}</blockquote>
                    ))}
                  </div>
                ))}
                {!analysis.aspects.length && (
                  <Empty
                    title={
                      analysis.supported
                        ? 'No explicit aspect detected'
                        : 'This language is not supported'
                    }
                  >
                    {analysis.supported
                      ? 'General praise or implicit references may not produce a result.'
                      : 'Use an English review for this version.'}
                  </Empty>
                )}
              </div>
              <div className="result-warnings">
                {analysis.warnings.map((warning) => (
                  <p key={warning}>
                    <CircleHelp size={13} />
                    {warning}
                  </p>
                ))}
              </div>
            </section>
          ))
        )}
      </div>
    </>
  )
}
export default AnalyseView
