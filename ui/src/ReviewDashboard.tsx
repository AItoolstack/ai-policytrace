import { PDFPane } from './PDFPane'
import { RecordPane } from './RecordPane'
import { useStore } from './store'
import logoUrl from './assets/ai-toolstack-logo.svg'

interface Props {
  sessionId: string
}

export function ReviewDashboard({ sessionId }: Props) {
  const sessionData = useStore((s) => s.sessionData)
  const reviewState = useStore((s) => s.reviewState)

  const verified = Object.values(reviewState).filter((r) => r.action === 'verify').length
  const overridden = Object.values(reviewState).filter((r) => r.action === 'override').length
  const provTotal = sessionData?.provenance.length ?? 0
  const fieldTotal = sessionData ? _countLeaves(sessionData.record) : 0

  return (
    <div className="flex flex-col h-screen overflow-hidden" style={{ backgroundColor: '#f1f5f9' }}>

      {/* ── Top bar ─────────────────────────────────────────────────── */}
      <header className="flex items-center justify-between px-6 py-3 bg-white border-b border-gray-200 shadow-sm z-10 flex-shrink-0">
        <div className="flex items-center gap-4">
          <a href="https://www.ai-toolstack.com/" target="_blank" rel="noopener noreferrer">
            <img src={logoUrl} alt="AI Tool Stack" className="h-6 w-auto" />
          </a>
          {/* Divider */}
          <span className="text-gray-200 select-none">|</span>
          <div className="flex items-center gap-2">
            <svg width="16" height="16" viewBox="0 0 28 28" fill="none" aria-hidden="true">
              <path d="M4 18L14 22L24 18" stroke="#1F2937" strokeWidth="2.5" strokeLinecap="round" strokeLinejoin="round"/>
              <path d="M4 14L14 18L24 14" stroke="#2563EB" strokeWidth="2.5" strokeLinecap="round" strokeLinejoin="round"/>
              <path d="M4 10L14 14L24 10L14 6L4 10Z" stroke="#008080" strokeWidth="2.5" strokeLinecap="round" strokeLinejoin="round"/>
            </svg>
            <span className="text-sm font-semibold" style={{ color: '#1F2937' }}>PolicyTrace</span>
          </div>
          <span className="text-xs text-gray-400 font-mono bg-gray-50 px-2 py-0.5 rounded-lg border border-gray-200">
            {sessionId.slice(0, 8)}…
          </span>
        </div>
        <div className="flex items-center gap-3 text-xs text-gray-500">
          <Stat label="Fields" value={fieldTotal} />
          <StatDivider />
          <Stat label="Located" value={provTotal} />
          <StatDivider />
          <Stat label="Verified" value={verified} color="#16a34a" />
          <StatDivider />
          <Stat label="Overridden" value={overridden} color="#2563EB" />
        </div>
      </header>

      {/* ── 2-column body ───────────────────────────────────────────── */}
      <div className="flex flex-1 overflow-hidden">
        <div className="w-1/2 border-r border-gray-200 flex flex-col overflow-hidden">
          <PDFPane sessionId={sessionId} />
        </div>
        <div className="w-1/2 flex flex-col overflow-hidden">
          <RecordPane sessionId={sessionId} />
        </div>
      </div>
    </div>
  )
}

function StatDivider() {
  return <span className="text-gray-200 select-none">·</span>
}

function Stat({
  label,
  value,
  color = '#374151',
}: {
  label: string
  value: number
  color?: string
}) {
  return (
    <span>
      {label}:{' '}
      <span className="font-semibold" style={{ color }}>{value}</span>
    </span>
  )
}

/** Recursively count leaf values in any nested object (mirrors backend _count_leaves). */
function _countLeaves(obj: unknown): number {
  if (Array.isArray(obj)) return obj.reduce((acc, v) => acc + _countLeaves(v), 0)
  if (obj && typeof obj === 'object')
    return Object.values(obj).reduce((acc: number, v) => acc + _countLeaves(v), 0)
  return 1
}
