import { useEffect, useRef, useState } from 'react'
import { Check, Database, Loader2, Upload, X } from 'lucide-react'
import { number, request } from '../api'

function ImportDialog({
  onClose,
  onComplete,
}: {
  onClose: () => void
  onComplete: (id: string, message: string) => void
}) {
  const [file, setFile] = useState<File | null>(null)
  const [name, setName] = useState('')
  const [preview, setPreview] = useState<{
    columns: string[]
    rows: number
    preview: Record<string, string>[]
  } | null>(null)
  const [mapping, setMapping] = useState<Record<string, string>>({
    text: '',
    product: '',
    brand: '',
    date: '',
    rating: '',
  })
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState('')
  const ref = useRef<HTMLDivElement>(null)
  useEffect(() => {
    const previous = document.activeElement as HTMLElement
    ref.current?.focus()
    function keyboard(event: KeyboardEvent) {
      if (event.key === 'Escape' && !busy) onClose()
      if (event.key === 'Tab') {
        const elements = ref.current?.querySelectorAll<HTMLElement>(
          'button:not(:disabled), input, select, [tabindex="0"]',
        )
        if (!elements?.length) return
        const first = elements[0],
          last = elements[elements.length - 1]
        if (event.shiftKey && document.activeElement === first) {
          event.preventDefault()
          last.focus()
        }
        if (!event.shiftKey && document.activeElement === last) {
          event.preventDefault()
          first.focus()
        }
      }
    }
    document.addEventListener('keydown', keyboard)
    return () => {
      document.removeEventListener('keydown', keyboard)
      previous?.focus()
    }
  }, [busy, onClose])
  async function choose(selected: File | undefined) {
    if (!selected) return
    setError('')
    setPreview(null)
    setFile(selected)
    setName(selected.name.replace(/\.csv$/i, ''))
    setBusy(true)
    try {
      const body = new FormData()
      body.append('file', selected)
      const data = await request<{
        columns: string[]
        rows: number
        preview: Record<string, string>[]
      }>('/api/import/preview', { method: 'POST', body })
      setPreview(data)
      const find = (options: string[]) =>
        data.columns.find((column) => options.includes(column.toLowerCase())) || ''
      setMapping({
        text: find(['text', 'body', 'review', 'reviews', 'review_text']),
        product: find(['product', 'product_name', 'phone', 'model']),
        brand: find(['brand']),
        date: find(['date', 'review_date']),
        rating: find(['rating', 'stars']),
      })
    } catch (error) {
      setError((error as Error).message)
    } finally {
      setBusy(false)
    }
  }
  async function submit() {
    if (!file) return
    setBusy(true)
    setError('')
    try {
      const body = new FormData()
      body.append('file', file)
      body.append('name', name)
      Object.entries(mapping).forEach(([key, value]) => body.append(`${key}_column`, value))
      const result = await request<{
        id: string
        accepted: number
        rejected: number
        duplicate: boolean
      }>('/api/datasets', { method: 'POST', body })
      onComplete(
        result.id,
        result.rejected
          ? `Imported ${number(result.accepted)} reviews; ${number(result.rejected)} rows were rejected or duplicates. Review the dataset manifest for details.`
          : '',
      )
    } catch (error) {
      setError((error as Error).message)
    } finally {
      setBusy(false)
    }
  }
  return (
    <div
      className="modal-backdrop"
      onMouseDown={(event) => {
        if (event.target === event.currentTarget && !busy) onClose()
      }}
    >
      <div
        className="modal"
        ref={ref}
        tabIndex={-1}
        role="dialog"
        aria-modal="true"
        aria-labelledby="import-heading"
      >
        <div className="modal-heading">
          <div>
            <span className="eyebrow">ADD TO YOUR WORKSPACE</span>
            <h2 id="import-heading">Import review data</h2>
          </div>
          <button
            className="icon-button"
            aria-label="Close import"
            onClick={onClose}
            disabled={busy}
          >
            <X size={20} />
          </button>
        </div>
        <p className="modal-description">
          Upload a UTF-8 CSV. Map the review text and any product details, then keep working with
          your data locally.
        </p>
        <label className="upload-area">
          <Upload size={25} />
          <strong>{file?.name || 'Choose a CSV file'}</strong>
          <span>Up to 16 MB · 10,000 rows</span>
          <input
            type="file"
            accept=".csv,text/csv"
            onChange={(event) => choose(event.target.files?.[0])}
            disabled={busy}
          />
        </label>
        {preview && (
          <>
            <label className="form-field">
              Dataset name
              <input
                value={name}
                maxLength={120}
                onChange={(event) => setName(event.target.value)}
              />
            </label>
            <div className="mapping-grid">
              {Object.entries(mapping).map(([key, value]) => (
                <label className="form-field" key={key}>
                  {key === 'text'
                    ? 'Review text *'
                    : `${key[0].toUpperCase()}${key.slice(1)} (optional)`}
                  <select
                    value={value}
                    onChange={(event) => setMapping({ ...mapping, [key]: event.target.value })}
                  >
                    <option value="">{key === 'text' ? 'Choose a column' : 'Not provided'}</option>
                    {preview.columns.map((column) => (
                      <option key={column} value={column}>
                        {column}
                      </option>
                    ))}
                  </select>
                </label>
              ))}
            </div>
            <div className="import-preview">
              <Check size={15} />
              <span>{number(preview.rows)} rows found · Original wording will be preserved.</span>
            </div>
          </>
        )}
        {error && (
          <div className="alert error" role="alert">
            {error}
          </div>
        )}
        <div className="modal-footer">
          <button className="button secondary" disabled={busy} onClick={onClose}>
            Cancel
          </button>
          <button
            className="button primary"
            disabled={!preview || !mapping.text || !name.trim() || busy}
            onClick={submit}
          >
            {busy ? <Loader2 className="spin" size={16} /> : <Database size={16} />}
            {busy ? 'Checking data…' : 'Import dataset'}
          </button>
        </div>
      </div>
    </div>
  )
}

export default ImportDialog
