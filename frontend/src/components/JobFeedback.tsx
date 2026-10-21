import { useState } from 'react'
import { Loader2, Square } from 'lucide-react'
import { phoneName, number, request } from '../api'
import type { Job } from '../api'
import { useRemote } from '../hooks/useRemote'

type Failures = {
  total: number
  items: { review_id: string; product_name: string; brand: string; text: string; reason: string }[]
}

export default function JobFeedback({
  base,
  job,
  busy,
  onRetry,
  onChanged,
}: {
  base: string
  job: Job | undefined
  busy: boolean
  onRetry: () => void
  onChanged: () => void
}) {
  const [stopping, setStopping] = useState(false)
  const [error, setError] = useState('')
  const [showFailures, setShowFailures] = useState(false)
  const failures = useRemote<Failures>(
    showFailures && job ? `${base}/jobs/${job.id}/failures?limit=100` : null,
  )
  if (!job) return null
  const active = ['queued', 'running'].includes(job.status)
  async function stop() {
    setStopping(true)
    setError('')
    try {
      await request(`${base}/jobs/${job!.id}/cancel`, { method: 'POST' })
      onChanged()
    } catch (error) {
      setError((error as Error).message)
    } finally {
      setStopping(false)
    }
  }
  return (
    <>
      {active && (
        <div className="job-progress" role="status">
          <Loader2 className="spin" size={17} />
          <span>
            {job.cancel_requested
              ? 'Stopping after the current review'
              : job.status === 'queued'
                ? 'Queued for analysis'
                : 'Analysing reviews'}{' '}
            <strong>
              {number(job.processed + job.failed)} / {number(job.total)}
            </strong>
          </span>
          <progress max={job.total || 1} value={job.processed + job.failed} />
          <button
            className="text-button"
            disabled={stopping || !!job.cancel_requested}
            onClick={stop}
          >
            <Square size={12} /> {stopping || job.cancel_requested ? 'Stopping…' : 'Stop analysis'}
          </button>
        </div>
      )}
      {['failed', 'interrupted'].includes(job.status) && (
        <div className={`alert job-notice ${job.status === 'failed' ? 'error' : 'info'}`}>
          <span>
            {job.error} {number(job.processed)} {job.processed === 1 ? 'result' : 'results'} saved
            in this attempt.
          </span>
          <button disabled={busy} onClick={onRetry}>
            {busy ? 'Starting…' : 'Resume unfinished reviews'}
          </button>
        </div>
      )}
      {!!job.failed && (
        <section className="panel job-failures">
          <button className="text-button" onClick={() => setShowFailures(!showFailures)}>
            {showFailures ? 'Hide' : 'Inspect'} {number(job.failed)} failed{' '}
            {job.failed === 1 ? 'review' : 'reviews'}
          </button>
          {showFailures && (
            <>
              {failures.loading && <p>Loading failure details…</p>}
              {failures.error && <p role="alert">{failures.error}</p>}
              {failures.data?.items.map((item) => (
                <article key={item.review_id}>
                  <strong>{phoneName(item.product_name, item.brand)}</strong>
                  <p>{item.text}</p>
                  <p className="failure-reason">{item.reason}</p>
                </article>
              ))}
              {failures.data && (
                <p className="muted">
                  Showing {failures.data.items.length} of {failures.data.total} recorded failures.
                  Resuming retries only unfinished reviews.
                </p>
              )}
            </>
          )}
        </section>
      )}
      {error && (
        <div className="alert error" role="alert">
          {error}
        </div>
      )}
    </>
  )
}
