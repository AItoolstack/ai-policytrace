import { useEffect, useState } from 'react'
import { useNavigate, useParams } from 'react-router-dom'
import { api } from './api'
import { ReviewDashboard } from './ReviewDashboard'
import { useStore } from './store'

/**
 * Route: /session/:sessionId
 *
 * Loads session data from the API on mount so the page survives a hard refresh
 * or a direct link (e.g. from a blog post).  If the session ID is not found the
 * user is redirected back to the upload page with a clear error message.
 */
export function SessionPage() {
  const { sessionId } = useParams<{ sessionId: string }>()
  const navigate = useNavigate()
  const setSession = useStore((s) => s.setSession)
  const sessionData = useStore((s) => s.sessionData)

  const [loading, setLoading] = useState(false)
  const [error, setError] = useState<string | null>(null)

  useEffect(() => {
    if (!sessionId) {
      navigate('/')
      return
    }

    // If the store already has data for this exact session (just navigated from
    // the upload page), skip the API call.
    if (sessionData?.session_id === sessionId) return

    setLoading(true)
    api.getSession(sessionId)
      .then((data) => {
        setSession(data)
        setLoading(false)
      })
      .catch(() => {
        setError(`Session "${sessionId.slice(0, 8)}…" not found or has expired.`)
        setLoading(false)
      })
  }, [sessionId]) // eslint-disable-line react-hooks/exhaustive-deps

  if (loading) {
    return (
      <div className="min-h-screen flex items-center justify-center" style={{ backgroundColor: '#f8fafc' }}>
        <div className="text-center space-y-3">
          <svg className="animate-spin h-8 w-8 mx-auto" viewBox="0 0 24 24" fill="none"
            style={{ color: '#008080' }}>
            <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4" />
            <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8v8z" />
          </svg>
          <p className="text-sm text-gray-500">Loading session…</p>
        </div>
      </div>
    )
  }

  if (error) {
    return (
      <div className="min-h-screen flex items-center justify-center" style={{ backgroundColor: '#f8fafc' }}>
        <div className="text-center space-y-4 max-w-sm">
          <p className="text-sm text-red-600 bg-red-50 border border-red-200 rounded-xl px-4 py-3">
            {error}
          </p>
          <button
            onClick={() => navigate('/')}
            className="text-sm font-medium underline"
            style={{ color: '#2563EB' }}
          >
            ← Back to upload
          </button>
        </div>
      </div>
    )
  }

  if (!sessionId) return null

  return <ReviewDashboard sessionId={sessionId} />
}
