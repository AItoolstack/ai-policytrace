import { useCallback, useEffect, useRef, useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { api } from './api'
import { useStore } from './store'
import type { SamplePack } from './types'
import { ExternalIcon, LINKS, Lockup, Spinner } from './Brand'

const PIPELINE = [
  ['01', 'parse', 'Docling: text and page positions'],
  ['02', 'mask', 'Presidio: names out before any model call'],
  ['03', 'classify', 'which document is which'],
  ['04', 'extract', 'typed record + the exact phrase read'],
  ['05', 'merge', 'a written rule picks the winner'],
  ['06', 'trace', 'each value back to its PDF line'],
  ['07', 'review', 'you verify, override or flag'],
] as const

export function UploadPage() {
  const navigate = useNavigate()
  const setSession = useStore((s) => s.setSession)
  const inputRef = useRef<HTMLInputElement>(null)

  const [loading, setLoading] = useState(false)
  const [step, setStep] = useState(0)
  const [error, setError] = useState<string | null>(null)
  const [files, setFiles] = useState<File[]>([])
  const [dragOver, setDragOver] = useState(false)
  const [samplePack, setSamplePack] = useState<SamplePack | null>(null)
  const [loadingSamples, setLoadingSamples] = useState(false)

  useEffect(() => {
    let isMounted = true
    api.getSamples()
      .then((pack) => { if (isMounted) setSamplePack(pack) })
      .catch(() => { if (isMounted) setSamplePack(null) })
    return () => { isMounted = false }
  }, [])

  // Advance the visual pipeline while the (synchronous) request runs.
  useEffect(() => {
    if (!loading) return
    setStep(0)
    const t = setInterval(() => setStep((s) => Math.min(s + 1, PIPELINE.length - 2)), 6000)
    return () => clearInterval(t)
  }, [loading])

  const addPdfFiles = useCallback((incoming: File[]) => {
    const pdfs = incoming.filter((f) => f.name.toLowerCase().endsWith('.pdf'))
    setFiles((prev) => {
      const names = new Set(prev.map((f) => f.name))
      return [...prev, ...pdfs.filter((f) => !names.has(f.name))]
    })
  }, [])

  const handleFiles = useCallback((incoming: FileList | null) => {
    if (!incoming) return
    addPdfFiles(Array.from(incoming))
  }, [addPdfFiles])

  const removeFile = (name: string) => setFiles((prev) => prev.filter((f) => f.name !== name))

  const handleLoadSamples = async () => {
    if (!samplePack?.files.length) return
    setLoadingSamples(true)
    setError(null)
    try {
      const demoFiles = await Promise.all(samplePack.files.map((sample) => api.downloadSampleFile(sample)))
      addPdfFiles(demoFiles)
    } catch (err: unknown) {
      setError(err instanceof Error ? err.message : 'Could not load the demo sample files.')
    } finally {
      setLoadingSamples(false)
    }
  }

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
      setError(err instanceof Error ? err.message : 'An unknown error occurred.')
      setLoading(false)
    }
  }

  return (
    <div className="min-h-screen flex flex-col bg-ink">
      {/* ── Top bar ─────────────────────────────────────────────── */}
      <header className="flex items-center justify-between gap-4 px-5 sm:px-8 h-16 border-b border-ink-700">
        <Lockup />
        <nav className="flex items-center gap-1 text-sm">
          <a href={LINKS.chapters} target="_blank" rel="noopener noreferrer"
            className="hidden sm:inline-flex items-center gap-1.5 px-3 py-2 rounded-lg text-ink-300 hover:text-ink-100 hover:bg-ink-800">
            How it’s built <ExternalIcon />
          </a>
          <a href={LINKS.github} target="_blank" rel="noopener noreferrer"
            className="inline-flex items-center gap-1.5 px-3 py-2 rounded-lg text-ink-300 hover:text-ink-100 hover:bg-ink-800">
            Source <ExternalIcon />
          </a>
        </nav>
      </header>

      {/* ── Body ────────────────────────────────────────────────── */}
      <main className="flex-1 grid-bg">
        <div className="mx-auto max-w-6xl px-5 sm:px-8 py-12 lg:py-20 grid gap-10 lg:gap-16 lg:grid-cols-[1.05fr_1fr] items-start">

          {/* Left: what this is */}
          <section className="space-y-7 lg:pt-4">
            <p className="inline-flex font-mono text-[12px] uppercase tracking-[0.06em] text-[#2F5FA8] bg-[#E8EFFA] rounded-full px-2.5 py-1">Reference system · Document AI</p>
            <h1 className="text-[34px] sm:text-[44px] leading-[1.08] font-semibold tracking-[-0.03em] text-ink-100">
              A policy pack in. One checked record out.
            </h1>
            <p className="text-[17px] leading-relaxed text-ink-300 max-w-[34rem]">
              Upload the Schedule, Certificate, Statement of Fact and policy booklet. PolicyTrace pulls the facts a
              claims handler needs into one typed record, settles disagreements between documents with a written rule,
              and links every value to the line in the PDF it came from.
            </p>

            <ol className="rounded-xl border border-ink-700 bg-white font-mono text-[13px] overflow-hidden" aria-label="Pipeline">
              {PIPELINE.map(([n, name, desc], i) => {
                const state = !loading ? 'idle' : i < step ? 'done' : i === step ? 'active' : 'idle'
                return (
                  <li key={n} className="flex items-center gap-4 px-4 py-2.5 border-b border-dashed border-ink-700 last:border-b-0">
                    <span className="w-6 text-ink-400">{n}</span>
                    <span className={`w-24 ${state === 'active' ? 'text-signal-deep' : 'text-ink-100'}`}>{name}</span>
                    <span className="flex-1 text-ink-400 truncate">{desc}</span>
                    <span className="w-14 text-right">
                      {state === 'done' && <span className="text-state-pass">ok</span>}
                      {state === 'active' && <span className="inline-flex text-signal-deep"><Spinner className="h-3.5 w-3.5" /></span>}
                    </span>
                  </li>
                )
              })}
            </ol>
          </section>

          {/* Right: upload card */}
          <section className="rounded-2xl border border-ink-700 bg-white p-5 sm:p-6 shadow-page" aria-label="Upload documents">
            <div
              role="button"
              tabIndex={0}
              aria-label="Add PDF files"
              onKeyDown={(e) => { if (e.key === 'Enter' || e.key === ' ') inputRef.current?.click() }}
              onDragOver={(e) => { e.preventDefault(); setDragOver(true) }}
              onDragLeave={() => setDragOver(false)}
              onDrop={(e) => { e.preventDefault(); setDragOver(false); handleFiles(e.dataTransfer.files) }}
              onClick={() => inputRef.current?.click()}
              className={`rounded-xl border border-dashed px-6 py-10 text-center cursor-pointer transition-colors ${
                dragOver ? 'border-signal bg-signal-tint' : 'border-ink-500 hover:border-ink-400 bg-ink-800'
              }`}
            >
              <svg className={`mx-auto mb-4 h-9 w-9 ${dragOver ? 'text-signal' : 'text-ink-400'}`} fill="none" viewBox="0 0 24 24"
                stroke="currentColor" strokeWidth={1.5} aria-hidden="true">
                <path strokeLinecap="round" strokeLinejoin="round" d="M12 16V4m0 0-4 4m4-4 4 4M4 16v2a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2v-2" />
              </svg>
              <p className="text-[15px] font-medium text-ink-100">
                Drop PDFs here or <span className="text-signal-deep underline decoration-signal underline-offset-2">browse</span>
              </p>
              <p className="mt-1.5 font-mono text-[12px] text-ink-400">Schedule · Certificate · Statement of Fact · Booklet</p>
              <input ref={inputRef} type="file" accept=".pdf" multiple className="hidden"
                onChange={(e) => handleFiles(e.target.files)} />
            </div>

            {samplePack?.files.length ? (
              <div className="mt-4 rounded-xl border border-ink-700 bg-ink-800 p-4">
                <div className="flex flex-col gap-3 sm:flex-row sm:items-center sm:justify-between">
                  <div>
                    <p className="text-sm font-medium text-ink-100">No documents to hand?</p>
                    <p className="mt-0.5 text-[13px] text-ink-300">
                      Load the synthetic demo pack{samplePack.expected_policy_number ? <> (<span className="font-mono">{samplePack.expected_policy_number}</span>)</> : null}. No real customer data.
                    </p>
                  </div>
                  <button type="button" onClick={handleLoadSamples} disabled={loadingSamples} className="btn-ghost text-sm shrink-0">
                    {loadingSamples ? <><Spinner /> Loading…</> : 'Load demo pack'}
                  </button>
                </div>
              </div>
            ) : null}

            {files.length > 0 && (
              <ul className="mt-4 space-y-2" aria-label="Selected files">
                {files.map((f) => (
                  <li key={f.name} className="flex items-center justify-between gap-3 rounded-lg border border-ink-700 bg-ink-800 px-3.5 py-2.5">
                    <div className="flex items-center gap-3 min-w-0">
                      <span className="shrink-0 rounded font-mono text-[10px] font-medium px-1.5 py-0.5 bg-ink-700 text-ink-300">PDF</span>
                      <span className="text-sm text-ink-200 truncate">{f.name}</span>
                    </div>
                    <button onClick={() => removeFile(f.name)} aria-label={`Remove ${f.name}`}
                      className="shrink-0 h-8 w-8 grid place-items-center rounded-md text-ink-400 hover:text-ink-100 hover:bg-ink-700">
                      <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" aria-hidden="true"><path d="M6 6l12 12M18 6 6 18" /></svg>
                    </button>
                  </li>
                ))}
              </ul>
            )}

            {error && (
              <div role="alert" className="mt-4 rounded-lg border border-state-flag/40 bg-state-flag/10 px-3.5 py-3 text-sm text-state-flag">
                {error}
              </div>
            )}

            <button onClick={handleSubmit} disabled={!files.length || loading} className="btn-signal w-full mt-5 text-[15px]">
              {loading ? <><Spinner /> Extracting · usually 2–3 min</> : <>Extract &amp; review{files.length ? ` ${files.length} file${files.length > 1 ? 's' : ''}` : ''}</>}
            </button>

            <p className="mt-4 text-[12px] leading-relaxed text-ink-400">
              Public demo. Use synthetic or redacted documents only.
            </p>
          </section>
        </div>
      </main>

      <footer className="border-t border-ink-700 px-5 sm:px-8 py-4 flex flex-wrap gap-x-6 gap-y-1 justify-between font-mono text-[12px] text-ink-400">
        <span>PolicyTrace · a reference system from <a className="text-ink-300 hover:text-signal-deep" href="https://www.ai-toolstack.com/" target="_blank" rel="noopener noreferrer">ai·toolstack</a></span>
        <span>Docling · Presidio · Groq · Instructor · FastAPI · React</span>
      </footer>
    </div>
  )
}
