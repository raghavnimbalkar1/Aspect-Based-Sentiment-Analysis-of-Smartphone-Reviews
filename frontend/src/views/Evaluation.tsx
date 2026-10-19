import { FlaskConical } from 'lucide-react'
import { number } from '../api'
import type { Evaluation } from '../api'
import { Empty } from '../components/common'
import { useRemote } from '../hooks/useRemote'

function EvaluationView() {
  const result = useRemote<Evaluation>('/api/evaluation')
  return (
    <>
      <div className="evaluation-intro">
        <span className="evaluation-icon">
          <FlaskConical size={24} />
        </span>
        <div>
          <h2>Models and measured results</h2>
          <p>
            Compare the rule baseline with the installed transformer. The transformer is a
            transferred checkpoint; smartphone accuracy has not been measured. Training our own
            classifier requires completed human training and validation labels.
          </p>
        </div>
        <span className="subtle-chip">PHASED DELIVERY</span>
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
              <span className="model-number">0{index + 1}</span>
              <span className={`status-chip ${model.status === 'available' ? 'ready' : ''}`}>
                {model.status === 'available'
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
      <section className="panel">
        <div className="panel-title">
          <div>
            <h2>Experiment results</h2>
            <p>Exact category–sentiment tuple F1 is the primary metric.</p>
          </div>
        </div>
        {!result.data?.reports.length ? (
          <Empty title="No measured experiments yet" icon={<FlaskConical size={26} />}>
            Complete independent annotation and run the training command to produce validation
            results. Test results remain locked until final model selection.
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
                  <th>Training sentences</th>
                </tr>
              </thead>
              <tbody>
                {result.data.reports.flatMap((report) =>
                  Object.entries(report.validation).map(([model, metrics]) => (
                    <tr key={`${report.experiment}-${model}`}>
                      <td>{report.experiment}</td>
                      <td>{model}</td>
                      <td>{metrics.tuple_micro.f1.toFixed(3)}</td>
                      <td>{metrics.presence_micro.f1.toFixed(3)}</td>
                      <td>{number(report.training_sentences)}</td>
                    </tr>
                  )),
                )}
              </tbody>
            </table>
          </div>
        )}
      </section>
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
            Review-level and near-duplicate groups stay in one partition. Star ratings are hidden
            from annotation tasks and are never used as aspect labels.
          </p>
        </section>
        <section className="panel">
          <h3>What can this baseline miss?</h3>
          <p>
            Implicit features, sarcasm, comparisons between phones, and complex opinion attachment.
            Supporting sentences help you inspect those errors.
          </p>
        </section>
      </div>
    </>
  )
}

export default EvaluationView
