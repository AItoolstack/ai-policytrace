import { PDFPane } from './PDFPane'
import { RecordPane } from './RecordPane'
import { useStore } from './store'
import { ExternalIcon, LINKS, Lockup } from './Brand'

interface Props {
  sessionId: string
}

export function ReviewDashboard({ sessionId }: Props) {
  const sessionData = useStore((s) => s.sessionData)
  const reviewState = useStore((s) => s.reviewState)

  const reviews = Object.values(reviewState)
  const verified = reviews.filter((r) => r.action === 'verify').length
  const overridden = reviews.filter((r) => r.action === 'override').length
  const flagged = reviews.filter((r) => r.action === 'reject').length
  const provTotal = sessionData?.provenance.length ?? 0
  const fieldTotal = sessionData ? _countLeaves(sessionData.record) : 0
  const reviewed = verified + overridden + flagged

  return (
    <div className="flex flex-col h-screen overflow-hidden bg-ink">
      {/* ── Top bar ─────────────────────────────────────────────── */}
      <header className="flex items-center justify-between gap-4 px-4 sm:px-6 h-14 border-b border-ink-700 flex-shrink-0">
        <div className="flex items-center gap-3 min-w-0">
          <Lockup />
          <span className="hidden md:inline font-mono text-[11px] text-ink-400 border border-ink-600 rounded-md px-2 py-1">
            session {sessionId.slice(0, 8)}
          </span>
        </div>

        <dl className="hidden lg:flex items-center gap-1 font-mono text-[12px]">
          <Stat label="fields" value={fieldTotal} />
          <Stat label="located" value={`${provTotal}`} />
          <Stat label="verified" value={verified} tone="pass" />
          <Stat label="overridden" value={overridden} tone="override" />
          <Stat label="flagged" value={flagged} tone="flag" />
        </dl>

        <div className="flex items-center gap-3">
          <div className="hidden sm:flex items-center gap-2" aria-label={`${reviewed} of ${fieldTotal} fields reviewed`}>
            <div className="h-1.5 w-28 rounded-full bg-ink-700 overflow-hidden">
              <div className="h-full bg-signal transition-all" style={{ width: `${fieldTotal ? Math.min(100, (reviewed / fieldTotal) * 100) : 0}%` }} />
            </div>
            <span className="font-mono text-[11px] text-ink-400">{reviewed}/{fieldTotal}</span>
          </div>
          <a href={LINKS.chapters} target="_blank" rel="noopener noreferrer"
            className="hidden md:inline-flex items-center gap-1.5 text-[13px] text-ink-300 hover:text-ink-100">
            How it’s built <ExternalIcon />
          </a>
        </div>
      </header>

      {/* ── 2-column body ───────────────────────────────────────── */}
      <div className="flex flex-1 overflow-hidden">
        <div className="w-1/2 border-r border-ink-700 flex flex-col overflow-hidden">
          <PDFPane sessionId={sessionId} />
        </div>
        <div className="w-1/2 flex flex-col overflow-hidden">
          <RecordPane sessionId={sessionId} />
        </div>
      </div>
    </div>
  )
}

const TONES = {
  pass: 'text-[#6FCF97]',
  override: 'text-[#A9B8E0]',
  flag: 'text-[#F2A35E]',
} as const

function Stat({ label, value, tone }: { label: string; value: number | string; tone?: keyof typeof TONES }) {
  return (
    <div className="flex items-baseline gap-1.5 px-2.5 py-1 rounded-md">
      <dd className={`font-medium ${tone ? TONES[tone] : 'text-ink-100'}`}>{value}</dd>
      <dt className="text-ink-400">{label}</dt>
    </div>
  )
}

/** Recursively count leaf values in any nested object (mirrors backend _count_leaves). */
function _countLeaves(obj: unknown): number {
  if (Array.isArray(obj)) return obj.reduce((acc, v) => acc + _countLeaves(v), 0)
  if (obj && typeof obj === 'object')
    return Object.values(obj).reduce((acc: number, v) => acc + _countLeaves(v), 0)
  return 1
}
