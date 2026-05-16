import { useCallback, useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { api } from './api'
import { useStore } from './store'
import logoUrl from './assets/ai-toolstack-logo.svg'

const BRAND = {
  dark: '#1F2937',
  blue: '#2563EB',
  teal: '#008080',
} as const

export function UploadPage() {
  const navigate = useNavigate()
  const setSession = useStore((s) => s.setSession)

  const [loading, setLoading] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [files, setFiles] = useState<File[]>([])
  const [dragOver, setDragOver] = useState(false)

  const handleFiles = useCallback((incoming: FileList | null) => {
    if (!incoming) return
    const pdfs = Array.from(incoming).filter((f) => f.name.toLowerCase().endsWith('.pdf'))
    setFiles((prev) => {
      const names = new Set(prev.map((f) => f.name))
      return [...prev, ...pdfs.filter((f) => !names.has(f.name))]
    })
  }, [])

  const removeFile = (name: string) =>
    setFiles((prev) => prev.filter((f) => f.name !== name))

  const handleSubmit = async () => {
    if (!files.length) return
    setLoading(true)
    setError(null)
    try {
      const resp = await api.processDocuments(files)
      const sessionData = await api.getSession(resp.session_id)
      setSession(sessionData)
      navigate(`/session/${resp.session_id}`)
    } catch (err: unknown) {
      const msg = err instanceof Error ? err.message : 'An unknown error occurred.'
      setError(msg)
      setLoading(false)
    }
  }

  return (
    <div className="min-h-screen flex flex-col" style={{ backgroundColor: '#f8fafc' }}>

      {/* ── Top nav ─────────────────────────────────────────────────── */}
      <header className="flex items-center justify-between px-8 py-4 border-b border-gray-200 bg-white">
        <a href="https://www.ai-toolstack.com/" target="_blank" rel="noopener noreferrer">
          <img src={logoUrl} alt="AI Tool Stack" className="h-7 w-auto" />
        </a>
        <span
          className="text-xs font-medium px-2 py-1 rounded-full"
          style={{ backgroundColor: '#f0fdfc', color: BRAND.teal }}
        >
          Beta
        </span>
      </header>

      {/* ── Hero ────────────────────────────────────────────────────── */}
      <main className="flex-1 flex flex-col items-center justify-center px-8 py-12">
        <div className="w-full max-w-lg">

          {/* Title */}
          <div className="mb-8 text-center">
            <div className="inline-flex items-center gap-2 mb-4">
              <svg width="28" height="28" viewBox="0 0 28 28" fill="none" aria-hidden="true">
                <path d="M4 18L14 22L24 18" stroke={BRAND.dark} strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"/>
                <path d="M4 14L14 18L24 14" stroke={BRAND.blue} strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"/>
                <path d="M4 10L14 14L24 10L14 6L4 10Z" stroke={BRAND.teal} strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"/>
              </svg>
              <h1 className="text-2xl font-bold tracking-tight" style={{ color: BRAND.dark }}>
                PolicyTrace
              </h1>
            </div>
            <p className="text-sm text-gray-500 leading-relaxed">
              Upload UK motor insurance PDFs — the pipeline classifies, extracts, and merges
              them into a verified Golden Record with full field-level provenance.
            </p>
          </div>

          {/* Drop zone */}
          <div
            onDragOver={(e) => { e.preventDefault(); setDragOver(true) }}
            onDragLeave={() => setDragOver(false)}
            onDrop={(e) => {
              e.preventDefault()
              setDragOver(false)
              handleFiles(e.dataTransfer.files)
            }}
            onClick={() => document.getElementById('file-input')?.click()}
            className="rounded-2xl border-2 border-dashed p-10 text-center cursor-pointer transition-all"
            style={{
              borderColor: dragOver ? BRAND.blue : '#d1d5db',
              backgroundColor: dragOver ? '#eff6ff' : '#ffffff',
            }}
          >
            <svg
              className="mx-auto mb-3 h-10 w-10 transition-colors"
              fill="none"
              viewBox="0 0 24 24"
              stroke="currentColor"
              style={{ color: dragOver ? BRAND.blue : '#9ca3af' }}
            >
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.5}
                d="M7 16a4 4 0 01-.88-7.903A5 5 0 1115.9 6L16 6a5 5 0 011 9.9M15 13l-3-3m0 0l-3 3m3-3v12" />
            </svg>
            <p className="text-sm font-medium text-gray-700">
              Drop PDF files here, or{' '}
              <span style={{ color: BRAND.blue }}>click to browse</span>
            </p>
            <p className="text-xs text-gray-400 mt-1">
              Schedule · Certificate · Statement of Fact · Policy Booklet
            </p>
            <input
              id="file-input"
              type="file"
              accept=".pdf"
              multiple
              className="hidden"
              onChange={(e) => handleFiles(e.target.files)}
            />
          </div>

          {/* File list */}
          {files.length > 0 && (
            <ul className="mt-4 space-y-2">
              {files.map((f) => (
                <li
                  key={f.name}
                  className="flex items-center justify-between bg-white border border-gray-200 rounded-xl px-4 py-2.5 text-sm shadow-sm"
                >
                  <div className="flex items-center gap-2 min-w-0">
                    <span
                      className="shrink-0 text-xs font-semibold px-1.5 py-0.5 rounded"
                      style={{ backgroundColor: '#fee2e2', color: '#991b1b' }}
                    >
                      PDF
                    </span>
                    <span className="text-gray-700 truncate">{f.name}</span>
                  </div>
                  <button
                    onClick={() => removeFile(f.name)}
                    className="text-gray-300 hover:text-red-500 ml-3 shrink-0 transition-colors"
                    aria-label={`Remove ${f.name}`}
                  >
                    ✕
                  </button>
                </li>
              ))}
            </ul>
          )}

          {/* Error */}
          {error && (
            <div className="mt-4 rounded-xl bg-red-50 border border-red-200 p-3 text-sm text-red-700">
              {error}
            </div>
          )}

          {/* CTA */}
          <button
            onClick={handleSubmit}
            disabled={!files.length || loading}
            className="mt-6 w-full py-3 px-6 rounded-xl font-semibold text-white transition-colors disabled:opacity-50 disabled:cursor-not-allowed"
            style={{ backgroundColor: loading ? BRAND.teal : BRAND.blue }}
          >
            {loading ? (
              <span className="flex items-center justify-center gap-2">
                <svg className="animate-spin h-4 w-4" viewBox="0 0 24 24" fill="none">
                  <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4" />
                  <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8v8z" />
                </svg>
                Extracting — this may take 60 s…
              </span>
            ) : (
              'Extract & Review'
            )}
          </button>

          {loading && (
            <p className="text-center text-xs text-gray-400 mt-3">
              Classifying documents · Masking PII · Calling Groq LLM · Building provenance index
            </p>
          )}
        </div>
      </main>

      {/* ── Footer ──────────────────────────────────────────────────── */}
      <footer className="text-center py-4 text-xs text-gray-400 border-t border-gray-200 bg-white">
        Built on{' '}
        <a
          href="https://www.ai-toolstack.com/"
          target="_blank"
          rel="noopener noreferrer"
          className="underline hover:text-gray-600 transition-colors"
        >
          AI Tool Stack
        </a>{' '}
        · Powered by Groq &amp; Docling
      </footer>
    </div>
  )
}
