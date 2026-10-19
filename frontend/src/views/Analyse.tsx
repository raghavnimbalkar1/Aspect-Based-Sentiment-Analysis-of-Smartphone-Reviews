import { useState } from 'react'
import { ArrowUpRight, CircleHelp, Loader2, MessageSquareText, Sparkles } from 'lucide-react'
import { names, number, request } from '../api'
import type { Analysis } from '../api'
import { Badge, Empty } from '../components/common'

function AnalyseView() {
  const [text, setText] = useState('')
  const [result, setResult] = useState<Analysis | null>(null)
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState('')
  async function submit() {
    setBusy(true)
    setError('')
    setResult(null)
    try {
      setResult(
        await request<Analysis>('/api/analyse', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ text }),
        }),
      )
    } catch (error) {
      setError((error as Error).message)
    } finally {
      setBusy(false)
    }
  }
  return (
    <div className="analyse-grid">
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
            setResult(null)
          }}
          maxLength={30000}
        />
        <div className="input-footer">
          <span>{number(text.length)} / 30,000 characters</span>
          <button className="button primary" disabled={!text.trim() || busy} onClick={submit}>
            {busy ? <Loader2 className="spin" size={16} /> : <Sparkles size={16} />}
            {busy ? 'Analysing…' : 'Analyse review'}
          </button>
        </div>
        <button
          className="text-button example-link"
          disabled={busy}
          onClick={() => {
            setText(
              'The camera takes sharp photos, but the battery barely lasts until lunch. The screen is bright and the phone gets hot while gaming.',
            )
            setResult(null)
          }}
        >
          Try a demonstration example
          <ArrowUpRight size={14} />
        </button>
        <p className="small-note">
          This example is illustrative and is not part of the held-out evaluation set.
        </p>
        {error && (
          <div className="inline-error" role="alert">
            {error}
          </div>
        )}
      </section>
      <section className="panel results-panel">
        <div className="panel-title">
          <div>
            <h2>Aspect breakdown</h2>
            <p>Each prediction links back to its supporting sentence.</p>
          </div>
        </div>
        {!result ? (
          <Empty title="The details will appear here" icon={<MessageSquareText size={26} />}>
            Add a review and select Analyse review.
          </Empty>
        ) : (
          <>
            <div className="analysis-result">
              {result.aspects.map((aspect) => (
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
              {!result.aspects.length && (
                <Empty
                  title={
                    result.supported
                      ? 'No explicit aspect detected'
                      : 'This language is not supported'
                  }
                >
                  {result.supported
                    ? 'The baseline needs explicit feature cues. General praise or implicit references may not produce a result.'
                    : 'Use an English review for this version.'}
                </Empty>
              )}
            </div>
            <div className="result-warnings">
              {result.warnings.map((warning) => (
                <p key={warning}>
                  <CircleHelp size={13} />
                  {warning}
                </p>
              ))}
            </div>
          </>
        )}
      </section>
    </div>
  )
}

export default AnalyseView
