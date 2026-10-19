import { useEffect, useState } from 'react'
import { Check, ChevronLeft, ChevronRight, Download, Save } from 'lucide-react'
import { names, request, states } from '../api'
import type { Sentiment } from '../api'
import { useRemote } from '../hooks/useRemote'
import { Empty } from '../components/common'

type Label = { label: Sentiment | 'absent'; reference: 'explicit' | 'implicit' | 'none' }
type Task = {
  sentence_id: string
  text: string
  position: number
  revision: number
  status: string
  annotator: string
  note: string
  labels: Record<string, Label>
}
type TaskSet = {
  id: string
  name: string
  total: number
  completed: number
  drafts: number
  pilot_train_only: boolean
}

export default function AnnotationView({
  onDirtyChange,
}: {
  onDirtyChange: (dirty: boolean) => void
}) {
  const [revision, refresh] = useState(0)
  const sets = useRemote<TaskSet[]>('/api/annotations', revision)
  const [setId, setSetId] = useState('')
  const [position, setPosition] = useState(0)
  const [savedTasks, setSavedTasks] = useState<Record<string, Task>>({})
  const [dirty, setDirty] = useState(false)
  function reportDirty(value: boolean) {
    setDirty(value)
    onDirtyChange(value)
  }
  const tasks = useRemote<Task[]>(setId ? `/api/annotations/${setId}/tasks` : null)
  const selected = sets.data?.find((item) => item.id === setId)
  const sourceTask = tasks.data?.[position]
  const task = sourceTask
    ? savedTasks[`${setId}:${sourceTask.sentence_id}`] || sourceTask
    : undefined
  useEffect(() => {
    if (sets.data?.length && !sets.data.some((item) => item.id === setId)) setSetId(sets.data[0].id)
  }, [sets.data, setId])
  useEffect(() => {
    setPosition(0)
  }, [setId])
  return (
    <>
      <div className="alert info">
        <span>
          Label each aspect from the sentence alone. Ratings and model predictions are hidden.
          Complete all ten states, including absent.
        </span>
      </div>
      {(sets.error || tasks.error) && (
        <div className="alert error" role="alert">
          {sets.error || tasks.error}
        </div>
      )}
      {!selected ? (
        <section className="panel">
          <Empty title="No annotation tasks loaded">
            Import a frozen task export with the annotation-import command in the project guide.
          </Empty>
        </section>
      ) : (
        <>
          <div className="annotation-toolbar">
            <label>
              Task collection
              <select
                aria-label="Annotation collection"
                disabled={dirty}
                value={setId}
                onChange={(event) => setSetId(event.target.value)}
              >
                {sets.data?.map((item) => (
                  <option key={item.id} value={item.id}>
                    {item.name}
                  </option>
                ))}
              </select>
            </label>
            <div>
              <strong>
                {selected.completed} / {selected.total}
              </strong>{' '}
              complete · {selected.drafts} drafts
              <br />
              <small>
                {selected.pilot_train_only
                  ? 'Training pilot · does not estimate test accuracy'
                  : 'Frozen study partitions'}
              </small>
            </div>
            <a
              className={`button secondary ${!selected.completed ? 'disabled-link' : ''}`}
              aria-disabled={!selected.completed}
              href={selected.completed ? `/api/annotations/${setId}/export` : undefined}
            >
              <Download size={16} />
              Export completed labels
            </a>
          </div>
          {task && (
            <SentenceEditor
              key={`${setId}-${task.sentence_id}-${task.revision}`}
              onDirtyChange={reportDirty}
              task={task}
              setId={setId}
              total={selected.total}
              onSaved={(updated) => {
                setSavedTasks((current) => ({
                  ...current,
                  [`${setId}:${updated.sentence_id}`]: updated,
                }))
                refresh((value) => value + 1)
              }}
              onMove={(next) => setPosition(next)}
            />
          )}
        </>
      )}
    </>
  )
}

function SentenceEditor({
  task,
  setId,
  total,
  onSaved,
  onMove,
  onDirtyChange,
}: {
  task: Task
  setId: string
  total: number
  onSaved: (task: Task) => void
  onMove: (position: number) => void
  onDirtyChange: (dirty: boolean) => void
}) {
  const [labels, setLabels] = useState(task.labels)
  const [annotator, setAnnotator] = useState(
    task.annotator || localStorage.getItem(`aspect.annotator.${setId}`) || '',
  )
  const [note, setNote] = useState(task.note)
  const [dirty, setDirty] = useState(false)
  useEffect(() => {
    onDirtyChange(dirty)
  }, [dirty])
  useEffect(() => {
    if (!dirty) return
    const warn = (event: BeforeUnloadEvent) => {
      event.preventDefault()
      event.returnValue = ''
    }
    window.addEventListener('beforeunload', warn)
    return () => window.removeEventListener('beforeunload', warn)
  }, [dirty])
  const [busy, setBusy] = useState(false)
  const [message, setMessage] = useState('')
  const [error, setError] = useState('')
  const [saved, setSaved] = useState(false)
  const [showHistory, setShowHistory] = useState(false)
  const history = useRemote<
    { revision: number; created_at: string; edit: { annotator: string; status: string } }[]
  >(showHistory ? `/api/annotations/${setId}/tasks/${task.sentence_id}/history` : null)
  function change(category: string, label: Label['label'] | '') {
    setDirty(true)
    setSaved(false)
    const next = { ...labels }
    if (!label) delete next[category]
    else next[category] = { label, reference: label === 'absent' ? 'none' : 'explicit' }
    setLabels(next)
  }
  async function save(complete: boolean) {
    setBusy(true)
    setError('')
    setMessage('')
    try {
      const updated = await request<Task>(`/api/annotations/${setId}/tasks/${task.sentence_id}`, {
        method: 'PUT',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          revision: task.revision,
          annotator,
          note,
          labels,
          status: complete ? 'adjudicated' : 'draft',
        }),
      })
      localStorage.setItem(`aspect.annotator.${setId}`, annotator)
      setDirty(false)
      setSaved(true)
      setMessage(complete ? 'Sentence marked complete.' : 'Draft saved.')
      onSaved(updated)
    } catch (error) {
      setError((error as Error).message)
    } finally {
      setBusy(false)
    }
  }
  return (
    <section className="panel annotation-editor">
      <div className="panel-title">
        <div>
          <h2>
            Sentence {task.position + 1} of {total}
          </h2>
          <p>
            {task.status === 'adjudicated'
              ? 'Completed'
              : task.revision
                ? 'Draft saved'
                : 'Awaiting your labels'}{' '}
            · revision {task.revision}
          </p>
        </div>
        <div className="annotation-navigation">
          <button
            aria-label="Previous sentence"
            disabled={!task.position || dirty || busy}
            onClick={() => onMove(task.position - 1)}
          >
            <ChevronLeft size={18} />
          </button>
          <button
            aria-label="Next sentence"
            disabled={task.position + 1 >= total || dirty || busy}
            onClick={() => onMove(task.position + 1)}
          >
            <ChevronRight size={18} />
          </button>
        </div>
      </div>
      <blockquote className="annotation-sentence">{task.text}</blockquote>
      <div className="annotation-instructions">
        <p>
          <strong>Absent</strong>: feature is not mentioned. <strong>Neutral</strong>: feature is
          mentioned as a fact, without an opinion. <strong>Mixed</strong>: both positive and
          negative opinions about the same feature.
        </p>
        <button
          className="text-button"
          disabled={busy}
          onClick={() => {
            const next = { ...labels }
            Object.keys(names).forEach((category) => {
              if (!next[category]) next[category] = { label: 'absent', reference: 'none' }
            })
            setLabels(next)
            setDirty(true)
            setSaved(false)
          }}
        >
          Mark remaining aspects absent
        </button>
      </div>
      <div className="annotation-labels">
        {Object.entries(names).map(([category, name]) => (
          <div className="annotation-label-row" key={category}>
            <label htmlFor={`label-${category}`}>{name}</label>
            <select
              id={`label-${category}`}
              value={labels[category]?.label || ''}
              disabled={busy}
              onChange={(event) => change(category, event.target.value as Label['label'] | '')}
            >
              <option value="">Choose a state</option>
              {['absent', ...states].map((state) => (
                <option key={state} value={state}>
                  {state[0].toUpperCase() + state.slice(1)}
                </option>
              ))}
            </select>
            <select
              aria-label={`${name} reference`}
              value={labels[category]?.reference || 'none'}
              disabled={busy || !labels[category] || labels[category].label === 'absent'}
              onChange={(event) => {
                setLabels({
                  ...labels,
                  [category]: {
                    ...labels[category],
                    reference: event.target.value as Label['reference'],
                  },
                })
                setDirty(true)
                setSaved(false)
              }}
            >
              {!labels[category] || labels[category].label === 'absent' ? (
                <option value="none">No reference</option>
              ) : (
                <>
                  <option value="explicit">Explicit mention</option>
                  <option value="implicit">Implicit reference</option>
                </>
              )}
            </select>
          </div>
        ))}
      </div>
      <div className="annotation-notes">
        <label>
          Your annotator name
          <input
            aria-label="Annotator name"
            value={annotator}
            maxLength={100}
            disabled={busy}
            onChange={(event) => {
              setAnnotator(event.target.value)
              setDirty(true)
            }}
          />
        </label>
        <label>
          Notes or ambiguity
          <textarea
            aria-label="Annotation notes"
            value={note}
            maxLength={3000}
            disabled={busy}
            onChange={(event) => {
              setNote(event.target.value)
              setDirty(true)
            }}
            placeholder="Explain an ambiguous label, if needed."
          />
        </label>
      </div>
      {error && (
        <div className="inline-error" role="alert">
          {error}
        </div>
      )}
      <div className="annotation-save">
        <span role="status">
          {dirty
            ? 'Unsaved changes · save before changing sentence'
            : saved
              ? message
              : 'Labels are saved locally. No suggestions are prefilled.'}
        </span>
        {dirty && (
          <button
            className="text-button"
            disabled={busy}
            onClick={() => {
              setLabels(task.labels)
              setAnnotator(
                task.annotator || localStorage.getItem(`aspect.annotator.${setId}`) || '',
              )
              setNote(task.note)
              setDirty(false)
              setError('')
            }}
          >
            Discard unsaved changes
          </button>
        )}
        <button
          className="button secondary"
          disabled={busy || !annotator.trim()}
          onClick={() => save(false)}
        >
          <Save size={16} />
          Save draft
        </button>
        <button
          className="button primary"
          disabled={busy || !annotator.trim() || Object.keys(labels).length !== 10}
          onClick={() => save(true)}
        >
          <Check size={16} />
          Mark complete
        </button>
      </div>
      <button
        className="text-button annotation-history-toggle"
        onClick={() => setShowHistory((value) => !value)}
      >
        {showHistory ? 'Hide' : 'View'} edit history
      </button>
      {showHistory && (
        <div className="small-note">
          {history.error ||
            (!history.data?.length
              ? 'No saved edits yet.'
              : history.data.map((edit) => (
                  <p key={edit.revision}>
                    Revision {edit.revision} · {edit.edit.annotator} · {edit.edit.status} ·{' '}
                    {new Date(edit.created_at).toLocaleString()}
                  </p>
                )))}
        </div>
      )}
    </section>
  )
}
