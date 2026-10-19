import { useState } from 'react'
import { FlaskConical } from 'lucide-react'
import { number } from '../api'
import type { Evaluation } from '../api'
import { Empty } from '../components/common'
import ExperimentRunner from '../components/ExperimentRunner'
import ReportDetails from '../components/ReportDetails'
import { useRemote } from '../hooks/useRemote'

function EvaluationView({ onModelsChanged }: { onModelsChanged: () => void }) {
  const [revision, refresh] = useState(0)
  const [focus, setFocus] = useState<{ experiment: string; model: string } | null>(null)
  const result = useRemote<Evaluation>('/api/evaluation', revision)
  const focusedReport = result.data?.reports.find(
    (report) => report.experiment === focus?.experiment,
  )
  function updated() {
    refresh((value) => value + 1)
    onModelsChanged()
  }
  return (
    <>
      <div className="evaluation-intro">
        <span className="evaluation-icon">
          <FlaskConical size={24} />
        </span>
        <div>
          <h2>Models and measured results</h2>
          <p>
            Inspect model results against frozen human or explicitly identified AI-assisted labels.
            Pretrained checkpoints and classifiers trained on your own labels are identified
            separately.
          </p>
        </div>
        <span className="subtle-chip">REPRODUCIBLE EXPERIMENTS</span>
      </div>
      {result.error && (
        <div className="alert error" role="alert">
          {result.error}
        </div>
      )}
      <div className="model-grid">
        {result.data?.models.map((model, index) => (
          <section key={model.id} className="panel model-card">
            <div className="model-card-top">
              <span className="model-number">{String(index + 1).padStart(2, '0')}</span>
              <span className={`status-chip ${model.available ? 'ready' : ''}`}>
                {model.available
                  ? 'Available locally'
                  : model.status === 'not_installed'
                    ? 'Setup required'
                    : 'Awaiting labels'}
              </span>
            </div>
            <h2>{model.name}</h2>
            <p>{model.description}</p>
            <code>{model.id}</code>
            {model.setup && !model.available && (
              <p className="small-note">
                Setup: <code>{model.setup}</code>
              </p>
            )}
          </section>
        ))}
      </div>
      <ExperimentRunner models={result.data?.models || []} onComplete={updated} />
      <section className="panel">
        <div className="panel-title">
          <div>
            <h2>Experiment results</h2>
            <p>
              Exact category–sentiment tuple F1 is the primary metric. Select a row to inspect it.
            </p>
          </div>
          <button className="text-button" onClick={updated}>
            Refresh results
          </button>
        </div>
        {!result.data?.reports.length ? (
          <Empty title="No measured experiments yet" icon={<FlaskConical size={26} />}>
            Complete a study's human validation labels, then compare installed models or train
            TF-IDF above. No scores are substituted for missing labels.
          </Empty>
        ) : (
          <div className="comparison-scroll">
            <table className="experiment-table">
              <thead>
                <tr>
                  <th>Experiment</th>
                  <th>Model</th>
                  <th>Tuple micro-F1</th>
                  <th>Presence F1</th>
                  <th>Validation sentences</th>
                  <th>Details</th>
                </tr>
              </thead>
              <tbody>
                {result.data.reports.flatMap((report) =>
                  Object.entries(report.validation).map(([model, metrics]) => (
                    <tr
                      key={`${report.experiment}-${model}`}
                      className={
                        focus?.experiment === report.experiment && focus.model === model
                          ? 'selected-report'
                          : ''
                      }
                    >
                      <td>
                        {report.experiment}
                        {report.evaluation_reference?.validation?.independent === false && (
                          <small className="support-note">AI-assisted diagnostic</small>
                        )}
                      </td>
                      <td>{model === 'tfidf-v1' ? report.model_id : model}</td>
                      <td>{metrics.tuple_micro.f1.toFixed(3)}</td>
                      <td>{metrics.presence_micro.f1.toFixed(3)}</td>
                      <td>{number(metrics.sentences)}</td>
                      <td>
                        <button
                          className="text-button"
                          aria-label={`Inspect ${model} in ${report.experiment}`}
                          onClick={() => setFocus({ experiment: report.experiment, model })}
                        >
                          Inspect
                        </button>
                      </td>
                    </tr>
                  )),
                )}
              </tbody>
            </table>
          </div>
        )}
      </section>
      {focusedReport && focus && (
        <ReportDetails report={focusedReport} model={focus.model} onClose={() => setFocus(null)} />
      )}
      <div className="method-cards">
        <section className="panel">
          <h3>What counts as correct?</h3>
          <p>
            A prediction must identify both the aspect and its sentiment. A correct aspect with the
            wrong sentiment counts as a false positive and a false negative.
          </p>
        </section>
        <section className="panel">
          <h3>What keeps evaluation honest?</h3>
          <p>
            Review and duplicate groups stay in one partition. Ratings and predictions stay hidden
            during annotation. Experiments preserve submitted label snapshots.
          </p>
        </section>
        <section className="panel">
          <h3>What can these models miss?</h3>
          <p>
            Implicit features, sarcasm, comparisons between phones and complex opinion attachment.
            Small or single-annotator datasets limit the conclusions.
          </p>
        </section>
      </div>
    </>
  )
}
export default EvaluationView
