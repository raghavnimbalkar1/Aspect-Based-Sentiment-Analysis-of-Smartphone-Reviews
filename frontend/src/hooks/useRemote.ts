import { useEffect, useState } from 'react'
import { request } from '../api'

export function useRemote<T>(url: string | null, revision = 0) {
  const [response, setResponse] = useState<{ url: string; data: T } | null>(null)
  const [error, setError] = useState('')
  const [loading, setLoading] = useState(false)
  useEffect(() => {
    if (!url) {
      setResponse(null)
      setLoading(false)
      setError('')
      return
    }
    const controller = new AbortController()
    setLoading(true)
    setError('')
    request<T>(url, { signal: controller.signal })
      .then((data) => setResponse({ url, data }))
      .catch((error) => {
        if (error.name !== 'AbortError') setError(error.message)
      })
      .finally(() => {
        if (!controller.signal.aborted) setLoading(false)
      })
    return () => controller.abort()
  }, [url, revision])
  return { data: response?.url === url ? response.data : null, error, loading }
}
