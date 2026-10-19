import { useState } from 'react'
import { Download } from 'lucide-react'
import { names } from '../api'
import { useRemote } from '../hooks/useRemote'

type Prediction = {
  sentence_id: string
  text: string
  category: string
  gold: string
  predicted: string
  error_type: string
  reference: string
  origin: string
}

export default function ErrorReview({ experiment, model }: { experiment: string; model: string }) {
  const [category, setCategory] = useState('')
  const [kind, setKind] = useState('errors')
  const [offset, setOffset] = useState(0)
  const endpoint = `/api/experiments/reports/${encodeURIComponent(experiment)}/predictions`
  const params = new URLSearchParams({ model, category, kind, offset: String(offset), limit: '10' })
  const results = useRemote<{ total: number; items: Prediction[] }>(`${endpoint}?${params}`)
  return (
    <div className="error-review">
      <h3 className="report-section-heading">Review validation errors</h3>
      <p className="report-description">
        Compare each prediction with the saved reference label. Missed aspects, extra aspects and
        sentiment mistakes are shown separately.
      </p>
      <div className="annotation-filters">
        <label>
          Aspect
          <select
            aria-label="Error review aspect"
            value={category}
            onChange={(event) => {
              setCategory(event.target.value)
              setOffset(0)
            }}
          >
            <option value="">All aspects</option>
            {Object.entries(names).map(([id, name]) => (
              <option key={id} value={id}>
                {name}
              </option>
            ))}
          </select>
        </label>
        <label>
          Result
          <select
            aria-label="Error review result"
            value={kind}
            onChange={(event) => {
              setKind(event.target.value)
              setOffset(0)
            }}
          >
            <option value="errors">All errors</option>
            <option value="false_negative">Missed aspect</option>
            <option value="false_positive">Extra aspect</option>
            <option value="wrong_sentiment">Wrong sentiment</option>
            <option value="all">All predictions</option>
          </select>
        </label>
        <a className="button secondary" href={`${endpoint}/download`}>
          <Download size={15} />
          Download all predictions
        </a>
      </div>
      {results.error && (
        <p className="inline-error" role="alert">
          {results.error}
        </p>
      )}
      {results.loading && (
        <p className="small-note" role="status">
          Loading predictions…
        </p>
      )}
      {results.data && (
        <>
          <p className="small-note">
            {results.data.total} matching category states · validation only
          </p>
          {!results.data.items.length && <p className="small-note">No matching predictions.</p>}
          {results.data.items.map((row) => (
            <article className="prediction-example" key={`${row.sentence_id}:${row.category}`}>
              <div>
                <strong>{names[row.category]}</strong>
                <span>{row.error_type.replaceAll('_', ' ')}</span>
              </div>
              <p>{row.text}</p>
              <small>
                Reference: <strong>{row.gold}</strong> (
                {row.origin === 'assisted' ? 'AI-assisted' : 'human'}) · Predicted:{' '}
                <strong>{row.predicted}</strong> · {row.reference} reference
              </small>
            </article>
          ))}
          <div className="prediction-navigation">
            <button
              className="button secondary"
              disabled={!offset}
              onClick={() => setOffset(Math.max(0, offset - 10))}
            >
              Previous
            </button>
            <span>
              {results.data.total ? offset + 1 : 0}–{Math.min(offset + 10, results.data.total)} of{' '}
              {results.data.total}
            </span>
            <button
              className="button secondary"
              disabled={offset + 10 >= results.data.total}
              onClick={() => setOffset(offset + 10)}
            >
              Next
            </button>
          </div>
        </>
      )}
    </div>
  )
}
