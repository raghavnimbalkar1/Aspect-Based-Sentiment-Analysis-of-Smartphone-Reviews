import { useEffect, useState } from 'react'
import { FlaskConical, Loader2, Play } from 'lucide-react'
import { request } from '../api'
import type { ExperimentRun, ModelSpec, TaskSet } from '../api'
import { useRemote } from '../hooks/useRemote'

export default function ExperimentRunner({
  models,
  onComplete,
}: {
  models: ModelSpec[]
  onComplete: () => void
}) {
  const [revision, refresh] = useState(0)
  const studies = useRemote<TaskSet[]>('/api/annotations', revision)
  const runs = useRemote<ExperimentRun[]>('/api/experiments', revision)
  const assistance = useRemote<
    { set_id: string; training_sentences: number; teacher: { name: string } }[]
  >('/api/experiments/training-assistance', revision)
  const [setId, setSetId] = useState('')
  const [kind, setKind] = useState('compare')
  const [trainingProfile, setTrainingProfile] = useState('flat')
  const [selectedModels, setSelectedModels] = useState(['rules-v1'])
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState('')
  const [useAssistance, setUseAssistance] = useState(false)
  const [useAssistedValidation, setUseAssistedValidation] = useState(false)
  const selectedId =
    setId ||
    studies.data?.find((study) => !study.pilot_train_only)?.id ||
    studies.data?.[0]?.id ||
    ''
  const study = studies.data?.find((item) => item.id === selectedId)
  const validation = study?.partitions.validation
  const hasAssistedValidation = !!validation?.completed_assisted
  const train = study?.partitions.train
  const savedAssistance = assistance.data?.find((item) => item.set_id === selectedId)
  const active = runs.data?.some((run) => ['queued', 'running'].includes(run.status))
  const completed =
    runs.data
      ?.filter((run) => run.status === 'completed')
      .map((run) => run.id)
      .join(',') || ''
  const eligible =
    !!validation?.total &&
    validation.completed === validation.total &&
    (!hasAssistedValidation || useAssistedValidation) &&
    (kind === 'compare'
      ? selectedModels.length > 0
      : !!train?.completed || (useAssistance && !!savedAssistance))
  const studyActive = runs.data?.some(
    (run) => run.set_id === selectedId && ['queued', 'running'].includes(run.status),
  )
  useEffect(() => {
    if (!active) return
    const timer = window.setInterval(() => refresh((value) => value + 1), 1500)
    return () => clearInterval(timer)
  }, [active])
  useEffect(() => {
    if (completed) onComplete()
  }, [completed])
  async function start() {
    setBusy(true)
    setError('')
    try {
      await request('/api/experiments', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          set_id: selectedId,
          kind,
          models: kind === 'compare' ? selectedModels : [],
          assisted_training: kind === 'train_tfidf' && useAssistance && !!savedAssistance,
          assisted_validation: useAssistedValidation && hasAssistedValidation,
          training_profile: kind === 'train_tfidf' ? trainingProfile : 'flat',
        }),
      })
      refresh((value) => value + 1)
    } catch (error) {
      setError((error as Error).message)
    } finally {
      setBusy(false)
    }
  }
  return (
    <section className="panel experiment-runner">
      <div className="panel-title">
        <div>
          <h2>Run a validation experiment</h2>
          <p>Use frozen reference labels with their human or AI-assisted origin recorded.</p>
        </div>
        <span className="subtle-chip">TEST SET LOCKED</span>
      </div>
      <div className="research-form-grid">
        <label className="form-field">
          Annotation study
          <select
            aria-label="Experiment annotation study"
            value={selectedId}
            disabled={busy}
            onChange={(event) => {
              setSetId(event.target.value)
              setUseAssistance(false)
              setUseAssistedValidation(false)
            }}
          >
            {!studies.data?.length && <option value="">Create an annotation study first</option>}
            {studies.data?.map((item) => (
              <option key={item.id} value={item.id}>
                {item.name}
                {item.pilot_train_only ? ' · training only' : ''}
              </option>
            ))}
          </select>
        </label>
        <label className="form-field">
          Experiment
          <select
            aria-label="Experiment type"
            value={kind}
            disabled={busy}
            onChange={(event) => setKind(event.target.value)}
          >
            <option value="compare">Compare installed models</option>
            <option value="train_tfidf">Train TF-IDF + logistic classifiers</option>
          </select>
        </label>
      </div>
      {kind === 'compare' ? (
        <fieldset className="experiment-models">
          <legend>Models to compare</legend>
          {models
            .filter((model) => model.id !== 'tfidf-supervised')
            .map((model) => (
              <label key={model.id}>
                <input
                  type="checkbox"
                  checked={selectedModels.includes(model.id)}
                  disabled={
                    busy ||
                    !model.available ||
                    (!selectedModels.includes(model.id) && selectedModels.length >= 3)
                  }
                  onChange={(event) =>
                    setSelectedModels((current) =>
                      event.target.checked
                        ? [...current, model.id]
                        : current.filter((id) => id !== model.id),
                    )
                  }
                />
                {model.name}
                {!model.available && <small>Setup required</small>}
              </label>
            ))}
        </fieldset>
      ) : (
        <>
          <label className="form-field">
            Training method
            <select
              aria-label="TF-IDF training method"
              value={trainingProfile}
              disabled={busy}
              onChange={(event) => setTrainingProfile(event.target.value)}
            >
              <option value="flat">Original · word features, five-state classifier</option>
              <option value="hierarchical">Two-stage · word + character features</option>
            </select>
          </label>
          <p className="runner-description">
            {trainingProfile === 'hierarchical'
              ? 'Learns whether each aspect is present, then classifies its sentiment using present examples. Word and character features fit training text only.'
              : 'Fits word TF-IDF on training text only and trains one five-state classifier per aspect.'}{' '}
            Compares with Rules + VADER and an always-absent reference. Each run keeps its own
            model.
          </p>
        </>
      )}
      {kind === 'train_tfidf' && savedAssistance && (
        <div className="runner-assistance">
          <label>
            <input
              type="checkbox"
              checked={useAssistance}
              disabled={busy}
              onChange={(event) => setUseAssistance(event.target.checked)}
            />
            Use saved assisted training labels ({savedAssistance.training_sentences} sentences)
          </label>
          <p>
            Generated by {savedAssistance.teacher.name}. These are machine labels, not human gold.
            Completed human training labels take precedence. AI-assisted validation requires
            explicit diagnostic mode; test always requires independent human labels.
          </p>
        </div>
      )}
      {hasAssistedValidation && (
        <div className="runner-assistance">
          <label>
            <input
              type="checkbox"
              checked={useAssistedValidation}
              disabled={busy}
              onChange={(event) => setUseAssistedValidation(event.target.checked)}
            />
            Use AI-assisted validation (diagnostic only)
          </label>
          <p>
            {validation?.completed_human || 0} human and {validation?.completed_assisted || 0}{' '}
            AI-assisted validation sentences. Scores measure agreement with these reference labels;
            they do not establish independent human-evaluated accuracy. Test remains human-only.
          </p>
        </div>
      )}
      <div className="experiment-readiness">
        <FlaskConical size={17} />
        <span>
          {!validation?.total
            ? 'A training pilot cannot estimate accuracy. Create a full study with validation sentences.'
            : validation.completed < validation.total
              ? `Complete all ${validation.total} validation sentences before running. ${validation.completed} of ${validation.total} complete.`
              : hasAssistedValidation && !useAssistedValidation
                ? 'This study has AI-assisted validation. Explicitly select diagnostic mode to use it.'
                : kind === 'train_tfidf' && !train?.completed && !(useAssistance && savedAssistance)
                  ? 'Complete human training labels, or explicitly select a prepared assisted training set.'
                  : `${validation.completed} validation sentences ready. Small samples and missing classes can give unstable scores.`}
        </span>
      </div>
      {(error || studies.error || runs.error) && (
        <div className="inline-error" role="alert">
          {error || studies.error || runs.error}
        </div>
      )}
      <div className="research-form-actions">
        <span>Each run saves a fixed label snapshot. Test scores are never calculated here.</span>
        <button
          className="button primary"
          disabled={busy || !eligible || studyActive}
          onClick={start}
        >
          {busy || studyActive ? <Loader2 className="spin" size={16} /> : <Play size={16} />}
          {studyActive ? 'Experiment queued / running' : busy ? 'Starting…' : 'Run experiment'}
        </button>
      </div>
      {!!runs.data?.length && (
        <div className="experiment-runs">
          {runs.data.slice(0, 5).map((run) => (
            <div key={run.id}>
              <div>
                <strong>{run.kind === 'compare' ? 'Model comparison' : 'TF-IDF training'}</strong>
                <span>
                  {run.study_name} · {new Date(run.created_at).toLocaleString()}
                </span>
                {run.error && <p role="alert">{run.error}</p>}
              </div>
              <span className={`status-chip ${run.status === 'completed' ? 'ready' : ''}`}>
                {['queued', 'running'].includes(run.status) && (
                  <Loader2 className="spin" size={12} />
                )}
                {run.status}
              </span>
            </div>
          ))}
        </div>
      )}
    </section>
  )
}
