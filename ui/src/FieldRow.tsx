import { useState } from 'react'
import type { FieldEntry, FieldReview } from './types'
import { useStore } from './store'

interface Props {
  entry: FieldEntry
  sessionId: string
  isActive: boolean
  review?: FieldReview
  onClick: () => void
}

export function FieldRow({ entry, sessionId, isActive, review, onClick }: Props) {
  const [editing, setEditing] = useState(false)
  const [editValue, setEditValue] = useState(entry.value ?? '')
  const verifyField = useStore((s) => s.verifyField)
  const overrideField = useStore((s) => s.overrideField)
  const rejectField = useStore((s) => s.rejectField)

  const displayValue = review?.action === 'override' && review.overridden_value != null
    ? review.overridden_value
    : entry.value

  const isVerified = review?.action === 'verify'
  const isRejected = review?.action === 'reject'
  const isOverridden = review?.action === 'override'

  const shell = isVerified
    ? 'border-state-pass/40 bg-state-pass-tint'
    : isRejected
    ? 'border-state-flag/45 bg-state-flag-tint'
    : isOverridden
    ? 'border-state-override/40 bg-state-override-tint'
    : isActive
    ? 'border-signal bg-paper-sheet ring-2 ring-signal/30'
    : 'border-paper-rule bg-paper-sheet hover:border-[#CFCBC0]'

  const handleSaveOverride = async () => {
    await overrideField(sessionId, entry.fieldPath, editValue)
    setEditing(false)
  }

  return (
    <div
      className={`group rounded-lg border px-3.5 py-2.5 cursor-pointer transition-colors shadow-sheet ${shell}`}
      onClick={onClick}
      role="button"
      tabIndex={0}
      aria-pressed={isActive}
      onKeyDown={(e) => { if ((e.key === 'Enter' || e.key === ' ') && !editing) { e.preventDefault(); onClick() } }}
    >
      <div className="flex items-start gap-3">
        <div className="flex-1 min-w-0">
          <div className="flex items-center gap-2 flex-wrap">
            <span className="text-[12px] font-medium text-paper-muted">{entry.label}</span>
            {isVerified && <StatusPill tone="pass">Verified</StatusPill>}
            {isOverridden && <StatusPill tone="override">Overridden</StatusPill>}
            {isRejected && <StatusPill tone="flag">Flagged</StatusPill>}
          </div>

          {editing ? (
            <div className="flex gap-2 mt-1.5" onClick={(e) => e.stopPropagation()}>
              <label className="sr-only" htmlFor={`edit-${entry.fieldPath}`}>New value for {entry.label}</label>
              <input
                id={`edit-${entry.fieldPath}`}
                autoFocus
                className="flex-1 min-w-0 text-[13px] text-paper-ink border border-paper-rule rounded-md px-2.5 py-1.5 bg-white focus:outline-none focus:border-signal focus:ring-2 focus:ring-signal/30"
                value={editValue}
                onChange={(e) => setEditValue(e.target.value)}
                onKeyDown={(e) => {
                  if (e.key === 'Enter') handleSaveOverride()
                  if (e.key === 'Escape') setEditing(false)
                }}
              />
              <button onClick={handleSaveOverride} className="text-[12px] font-medium px-3 rounded-md bg-ink text-ink-100 hover:bg-ink-700">Save</button>
              <button onClick={() => setEditing(false)} className="text-[12px] font-medium px-3 rounded-md border border-paper-rule text-paper-ink hover:bg-paper">Cancel</button>
            </div>
          ) : (
            <p className="text-[14px] text-paper-ink mt-0.5 truncate font-medium" title={displayValue ?? undefined}>
              {displayValue != null
                ? formatValue(displayValue, entry.fieldPath, isOverridden)
                : <span className="text-paper-muted italic font-normal">Not extracted</span>}
            </p>
          )}

          {!editing && (
            entry.provenance ? (
              <p className="mt-1 font-mono text-[11px] text-paper-muted truncate">
                {shortName(entry.provenance.source_filename)} · p.{entry.provenance.location.page} · “{entry.provenance.matched_text.slice(0, 56)}{entry.provenance.matched_text.length > 56 ? '…' : ''}”
              </p>
            ) : (
              <p className="mt-1 font-mono text-[11px] text-[#9A4321]">no source location · check manually</p>
            )
          )}
        </div>

        <div className="flex items-center gap-1 flex-shrink-0" onClick={(e) => e.stopPropagation()}>
          {entry.provenance && <ConfidenceBadge score={entry.provenance.match_score} />}

          <IconButton label={`Verify ${entry.label}`} active={isVerified} tone="pass"
            onClick={() => verifyField(sessionId, entry.fieldPath)}>
            <path d="M5 12.5l4.5 4.5L19 7.5" />
          </IconButton>
          <IconButton label={`Override ${entry.label}`} active={isOverridden} tone="override"
            onClick={() => { setEditValue(displayValue ?? ''); setEditing(true) }}>
            <path d="M4 20h4L19 9a2.8 2.8 0 0 0-4-4L4 16v4z" />
          </IconButton>
          <IconButton label={`Flag ${entry.label} for review`} active={isRejected} tone="flag"
            onClick={() => rejectField(sessionId, entry.fieldPath)}>
            <path d="M5 21V4h11l-1.5 4L16 12H5" />
          </IconButton>
        </div>
      </div>
    </div>
  )
}

const MONTHS = ['Jan', 'Feb', 'Mar', 'Apr', 'May', 'Jun', 'Jul', 'Aug', 'Sep', 'Oct', 'Nov', 'Dec']
const MONEY_PATH = /(excess|premium|optional_extras)/

/** Human-readable display of a stored value. The raw value stays in the title attribute. */
function formatValue(value: string, fieldPath: string, isOverride: boolean): string {
  if (isOverride) return value
  const dt = value.match(/^(\d{4})-(\d{2})-(\d{2})(?:T(\d{2}):(\d{2}))?/)
  if (dt) {
    const [, y, m, d, hh, mm] = dt
    const date = `${Number(d)} ${MONTHS[Number(m) - 1]} ${y}`
    return hh != null ? `${date}, ${hh}:${mm}` : date
  }
  if (value === 'true') return 'Yes'
  if (value === 'false') return 'No'
  if (MONEY_PATH.test(fieldPath) && /^-?\d+(\.\d+)?$/.test(value)) {
    return `£${Number(value).toLocaleString('en-GB', { minimumFractionDigits: 2, maximumFractionDigits: 2 })}`
  }
  if (fieldPath.endsWith('annual_mileage') && /^\d+$/.test(value)) {
    return `${Number(value).toLocaleString('en-GB')} miles`
  }
  return value
}

function shortName(filename: string) {
  return filename.replace(/\.pdf$/i, '').replace(/ - Demo$/i, '')
}

const TONE = {
  pass: { on: 'bg-state-pass text-white', hover: 'hover:text-state-pass hover:bg-state-pass-tint' },
  override: { on: 'bg-state-override text-white', hover: 'hover:text-state-override hover:bg-state-override-tint' },
  flag: { on: 'bg-state-flag text-white', hover: 'hover:text-state-flag hover:bg-state-flag-tint' },
} as const

function IconButton({ label, active, tone, onClick, children }: {
  label: string; active: boolean; tone: keyof typeof TONE; onClick: () => void; children: React.ReactNode
}) {
  return (
    <button
      type="button"
      title={label}
      aria-label={label}
      aria-pressed={active}
      onClick={onClick}
      className={`h-8 w-8 grid place-items-center rounded-md transition-colors ${
        active ? TONE[tone].on : `text-paper-muted ${TONE[tone].hover}`
      }`}
    >
      <svg width="15" height="15" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2"
        strokeLinecap="round" strokeLinejoin="round" aria-hidden="true">{children}</svg>
    </button>
  )
}

function StatusPill({ tone, children }: { tone: keyof typeof TONE; children: React.ReactNode }) {
  const cls = tone === 'pass' ? 'text-state-pass bg-state-pass/10'
    : tone === 'override' ? 'text-state-override bg-state-override/10'
    : 'text-state-flag bg-state-flag/10'
  return <span className={`font-mono text-[10px] font-medium uppercase tracking-[0.08em] px-1.5 py-0.5 rounded ${cls}`}>{children}</span>
}

function ConfidenceBadge({ score }: { score: number }) {
  const pct = Math.round(score * 100)
  const cls = pct >= 90 ? 'text-state-pass border-state-pass/30'
    : pct >= 75 ? 'text-signal-deep border-signal/50'
    : 'text-state-flag border-state-flag/40'
  return (
    <span className={`font-mono text-[11px] px-1.5 py-0.5 rounded border bg-white mr-1 ${cls}`} title="Citation match score">
      {pct}%
    </span>
  )
}
