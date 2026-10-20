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
  const [partition, setPartition] = useState<'validation' | 'test'>('validation')
  const [focus, setFocus] = useState<{ experiment: string; model: string } | null>(null)
  const result = useRemote<Evaluation>('/api/evaluation', revision)
  const focusedReport = result.data?.reports.find(
    (report) => report.experiment === focus?.experiment,
  )
  const reports = result.data?.reports.filter((report) => !!report[partition]) || []
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
      {!!result.data?.report_errors?.length && (
        <div className="alert error" role="alert">
          {result.data.report_errors.length} local report(s) could not be opened:{' '}
          {result.data.report_errors.map((item) => item.experiment).join(', ')}. Check the saved
          artifacts. Valid reports remain available.
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
            {model.development_tuned && (
              <p className="small-note">Developed using inspected diagnostic examples.</p>
            )}
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
        <label className="form-field report-partition">
          Results partition
          <select
            aria-label="Results partition"
            value={partition}
            onChange={(event) => {
              setPartition(event.target.value as 'validation' | 'test')
              setFocus(null)
            }}
          >
            <option value="validation">Validation and development diagnostics</option>
            <option value="test">Final test results</option>
          </select>
        </label>
        {!reports.length ? (
          <Empty
            title={
              partition === 'test' ? 'No final test results yet' : 'No measured experiments yet'
            }
            icon={<FlaskConical size={26} />}
          >
            {partition === 'test'
              ? 'No final test evaluation is available. Complete every frozen test sentence with human labels, then run the documented final-test command. Selecting this view never runs test inference.'
              : "Complete a study's validation labels, then compare installed models or train TF-IDF above. No scores are substituted for missing labels."}
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
                  <th>{partition === 'test' ? 'Test' : 'Validation'} sentences</th>
                  <th>Details</th>
                </tr>
              </thead>
              <tbody>
                {reports.flatMap((report) =>
                  Object.entries(report[partition]!).map(([model, metrics]) => (
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
                        {partition === 'test' && (
                          <small className="support-note">
                            {report.evaluation_coverage?.test?.complete
                              ? 'Complete frozen test partition'
                              : 'Test coverage unverified'}
                          </small>
                        )}
                        {report.evaluation_reference?.[partition]?.independent === false && (
                          <small className="support-note">AI-assisted diagnostic</small>
                        )}
                        {partition === 'validation' &&
                          report.development?.reference_previously_inspected && (
                            <small className="support-note">Development comparison</small>
                          )}
                      </td>
                      <td>{['tfidf-v1', 'tfidf-v2'].includes(model) ? report.model_id : model}</td>
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
        <ReportDetails
          report={focusedReport}
          model={focus.model}
          partition={partition}
          onClose={() => setFocus(null)}
        />
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
