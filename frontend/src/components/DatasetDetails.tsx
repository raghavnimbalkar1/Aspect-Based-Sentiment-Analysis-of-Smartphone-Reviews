import { useState } from 'react'
import { Download } from 'lucide-react'
import { number } from '../api'
import { useRemote } from '../hooks/useRemote'

type Details = {
  id: string
  name: string
  source: string
  accepted: number
  rejected: number
  fingerprint: string
  manifest: {
    input_rows?: number
    rejected?: Record<string, number>
    rejection_examples?: { row: number; reason: string }[]
    column_mapping?: Record<string, string>
    scope?: string
  }
}

export default function DatasetDetails({ base }: { base: string }) {
  const [open, setOpen] = useState(false)
  const result = useRemote<Details>(open ? base : null)
  return (
    <details
      className="panel dataset-details"
      onToggle={(event) => setOpen(event.currentTarget.open)}
    >
      <summary>Dataset details and import checks</summary>
      {result.error && (
        <p className="inline-error" role="alert">
          {result.error}
        </p>
      )}
      {open && !result.data && !result.error && <p role="status">Loading dataset details…</p>}
      {result.data && (
        <>
          <div className="panel-title">
            <div>
              <h2>{result.data.name}</h2>
              <p>
                {number(result.data.accepted)} accepted reviews · {number(result.data.rejected)}{' '}
                excluded rows
              </p>
            </div>
            <a className="button secondary" href={`${base}/manifest`}>
              <Download size={15} /> Download manifest
            </a>
          </div>
          <p className="small-note">
            Source: {result.data.source}. {result.data.manifest.scope}
          </p>
          <p className="small-note">
            Dataset fingerprint: <code>{result.data.fingerprint}</code>
          </p>
          {!!result.data.manifest.rejected && (
            <ul>
              {Object.entries(result.data.manifest.rejected).map(([reason, count]) => (
                <li key={reason}>
                  {reason.replaceAll('_', ' ')}: {number(count)}
                </li>
              ))}
            </ul>
          )}
          {!!result.data.manifest.rejection_examples?.length && (
            <div className="comparison-scroll">
              <table className="experiment-table">
                <thead>
                  <tr>
                    <th>CSV row</th>
                    <th>Reason</th>
                  </tr>
                </thead>
                <tbody>
                  {result.data.manifest.rejection_examples.map((example) => (
                    <tr key={example.row}>
                      <td>{example.row}</td>
                      <td>{example.reason}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}
          {!!result.data.manifest.column_mapping && (
            <p className="small-note">
              Mapped columns:{' '}
              {Object.entries(result.data.manifest.column_mapping)
                .filter(([, column]) => column)
                .map(([field, column]) => `${field}: ${column}`)
                .join(', ')}
              .
            </p>
          )}
        </>
      )}
    </details>
  )
}
