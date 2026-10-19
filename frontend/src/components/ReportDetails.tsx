import { Download, X } from 'lucide-react'
import { names, number, states } from '../api'
import type { ExperimentReport } from '../api'

export default function ReportDetails({
  report,
  model,
  onClose,
}: {
  report: ExperimentReport
  model: string
  onClose: () => void
}) {
  const metrics = report.validation[model]
  const labels = ['absent', ...states]
  return (
    <section className="panel report-details" aria-label="Selected experiment details">
      <div className="panel-title">
        <div>
          <h2>Validation detail</h2>
          <p>
            {report.experiment} · {model === 'tfidf-v1' ? report.model_id : model}
          </p>
        </div>
        <button aria-label="Close experiment details" className="icon-button" onClick={onClose}>
          <X size={18} />
        </button>
      </div>
      <div className="report-metrics">
        {[
          ['Tuple precision', metrics.tuple_micro.precision],
          ['Tuple recall', metrics.tuple_micro.recall],
          ['Tuple micro-F1', metrics.tuple_micro.f1],
          ['Presence F1', metrics.presence_micro.f1],
        ].map(([label, value]) => (
          <div key={label}>
            <span>{label}</span>
            <strong>{(value as number).toFixed(3)}</strong>
          </div>
        ))}
      </div>
      <div className="report-context">
        <span>
          {number(metrics.sentences)} validation sentences · {number(metrics.pairs)} category states
          · {number(report.training_sentences)} local training sentences
        </span>
        <a
          className="button secondary"
          href={`/api/experiments/reports/${encodeURIComponent(report.experiment)}`}
        >
          <Download size={15} />
          Download report JSON
        </a>
      </div>
      <h3 className="report-section-heading">Results by aspect</h3>
      <div className="comparison-scroll">
        <table className="experiment-table">
          <thead>
            <tr>
              <th>Aspect</th>
              <th>Gold mentions</th>
              <th>Predicted mentions</th>
              <th>Precision</th>
              <th>Recall</th>
              <th>Tuple F1</th>
            </tr>
          </thead>
          <tbody>
            {Object.entries(metrics.per_category).map(([category, score]) => (
              <tr key={category}>
                <th>{names[category]}</th>
                <td>{number(score.gold_support)}</td>
                <td>{number(score.predicted_support)}</td>
                <td>{score.precision.toFixed(3)}</td>
                <td>{score.recall.toFixed(3)}</td>
                <td>
                  {score.f1.toFixed(3)}
                  {score.gold_support === 0 && score.predicted_support === 0 && (
                    <small className="support-note">No examples</small>
                  )}
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
      <h3 className="report-section-heading">State confusion matrix</h3>
      <p className="report-description">
        Rows are human labels; columns are predictions. Includes absent states across all ten
        categories. Cell shading is relative to its row.
      </p>
      <div className="comparison-scroll">
        <table className="confusion-table">
          <thead>
            <tr>
              <th>Human ↓ / predicted →</th>
              {labels.map((label) => (
                <th key={label}>{label}</th>
              ))}
            </tr>
          </thead>
          <tbody>
            {labels.map((gold) => {
              const row = metrics.confusion_matrix[gold]
              const total = Object.values(row).reduce((sum, value) => sum + value, 0)
              return (
                <tr key={gold}>
                  <th>{gold}</th>
                  {labels.map((predicted) => (
                    <td
                      key={predicted}
                      style={{
                        background: row[predicted]
                          ? `rgba(79,141,118,${0.08 + (0.55 * row[predicted]) / total})`
                          : undefined,
                      }}
                      title={`${row[predicted]} examples; ${total ? Math.round((100 * row[predicted]) / total) : 0}% of ${gold} labels`}
                    >
                      {number(row[predicted])}
                    </td>
                  ))}
                </tr>
              )
            })}
          </tbody>
        </table>
      </div>
      <div className="report-provenance">
        <span>
          Label file SHA-256{' '}
          <code title={report.annotations_sha256}>{report.annotations_sha256.slice(0, 16)}…</code>
        </span>
        <span>
          Manifest SHA-256{' '}
          <code title={report.manifest_sha256}>{report.manifest_sha256.slice(0, 16)}…</code>
        </span>
        <span>
          {report.test_evaluated
            ? 'This report also contains an explicitly requested test evaluation.'
            : 'Test partition not evaluated.'}
        </span>
      </div>
      {report.warnings?.map((warning) => (
        <p className="small-note report-warning" key={warning}>
          {warning}
        </p>
      ))}
    </section>
  )
}
