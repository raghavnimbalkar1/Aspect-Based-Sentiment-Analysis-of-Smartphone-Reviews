import { useState } from 'react'
import { ClipboardPlus, Loader2 } from 'lucide-react'
import { request } from '../api'
import type { Dataset, TaskSet } from '../api'
import { useRemote } from '../hooks/useRemote'

export default function CreateStudy({
  onCreated,
  onClose,
}: {
  onCreated: (study: TaskSet) => void
  onClose: () => void
}) {
  const datasets = useRemote<Dataset[]>('/api/datasets')
  const [datasetId, setDatasetId] = useState('')
  const [name, setName] = useState('Smartphone annotation study')
  const [sentences, setSentences] = useState(300)
  const [pilot, setPilot] = useState(false)
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState('')
  const source = datasetId || datasets.data?.[0]?.id || ''
  async function submit(event: React.FormEvent) {
    event.preventDefault()
    setBusy(true)
    setError('')
    try {
      const study = await request<TaskSet>('/api/annotations/studies', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ dataset_id: source, name, sentences, pilot }),
      })
      onCreated(study)
    } catch (error) {
      setError((error as Error).message)
    } finally {
      setBusy(false)
    }
  }
  return (
    <section className="panel study-creator">
      <div className="panel-title">
        <div>
          <h2>Create an annotation study</h2>
          <p>Sample complete English reviews and freeze duplicate groups before labeling.</p>
        </div>
        <ClipboardPlus size={21} />
      </div>
      <form onSubmit={submit}>
        <div className="research-form-grid">
          <label className="form-field">
            Source dataset
            <select
              aria-label="Study source dataset"
              value={source}
              disabled={busy}
              onChange={(event) => setDatasetId(event.target.value)}
            >
              {!datasets.data?.length && <option value="">Import reviews first</option>}
              {datasets.data?.map((dataset) => (
                <option key={dataset.id} value={dataset.id}>
                  {dataset.name}
                </option>
              ))}
            </select>
          </label>
          <label className="form-field">
            Study name
            <input
              aria-label="Study name"
              required
              maxLength={120}
              value={name}
              disabled={busy}
              onChange={(event) => setName(event.target.value)}
            />
          </label>
          <label className="form-field">
            Study type
            <select
              aria-label="Study type"
              value={pilot ? 'pilot' : 'full'}
              disabled={busy}
              onChange={(event) => setPilot(event.target.value === 'pilot')}
            >
              <option value="full">Full study · train / validation / test</option>
              <option value="pilot">Training pilot only</option>
            </select>
          </label>
          <label className="form-field">
            Sentence target
            <input
              aria-label="Study sentence target"
              type="number"
              required
              min={1}
              max={2000}
              value={sentences}
              disabled={busy}
              onChange={(event) => setSentences(Number(event.target.value))}
            />
          </label>
        </div>
        <p className="small-note">
          The final count may exceed the target to keep reviews complete. No labels are prefilled.{' '}
          {pilot
            ? 'A training pilot cannot produce validation scores.'
            : 'Partitions follow frozen review/duplicate groups; small samples may contain few validation or test examples.'}
        </p>
        {(error || datasets.error) && (
          <div className="inline-error" role="alert">
            {error || datasets.error}
          </div>
        )}
        <div className="research-form-actions">
          <span role="status">
            {busy
              ? 'Preparing tasks in the local work queue. This may take a minute…'
              : 'Existing collections and labels are preserved.'}
          </span>
          <button type="button" className="button secondary" disabled={busy} onClick={onClose}>
            Cancel
          </button>
          <button
            type="submit"
            className="button primary"
            disabled={busy || !source || !name.trim() || !sentences}
          >
            {busy ? <Loader2 className="spin" size={16} /> : <ClipboardPlus size={16} />}
            {busy ? 'Preparing…' : 'Create study'}
          </button>
        </div>
      </form>
    </section>
  )
}
