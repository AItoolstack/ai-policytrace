import { type CSSProperties, useState } from 'react'
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

  const isVerified  = review?.action === 'verify'
  const isRejected  = review?.action === 'reject'
  const isOverridden = review?.action === 'override'

  const borderStyle: CSSProperties = isVerified
    ? { borderColor: '#16a34a', backgroundColor: '#f0fdf4' }
    : isRejected
    ? { borderColor: '#fca5a5', backgroundColor: '#fef2f2' }
    : isOverridden
    ? { borderColor: '#2563EB', backgroundColor: '#eff6ff' }
    : isActive
    ? { borderColor: '#008080', backgroundColor: '#f0fdfc' }
    : { borderColor: 'transparent', backgroundColor: '#ffffff' }

  const handleSaveOverride = async () => {
    await overrideField(sessionId, entry.fieldPath, editValue)
    setEditing(false)
  }

  return (
    <div
      className="rounded-lg border px-3 py-2 cursor-pointer transition-all hover:shadow-sm"
      style={borderStyle}
      onClick={onClick}
    >
      <div className="flex items-start gap-2">
        {/* Label + value */}
        <div className="flex-1 min-w-0">
          <div className="flex items-center gap-2 flex-wrap">
            <span className="text-xs font-semibold text-gray-500 shrink-0">
              {entry.label}
            </span>
            {isVerified && (
              <span className="inline-flex items-center gap-0.5 text-xs text-green-700 font-medium">
                <CheckIcon /> Verified
              </span>
            )}
            {isOverridden && (
              <span className="text-xs text-blue-700 font-medium">Overridden</span>
            )}
            {isRejected && (
              <span className="text-xs text-red-600 font-medium">Flagged</span>
            )}
          </div>

          {/* Value */}
          {editing ? (
            <div
              className="flex gap-2 mt-1"
              onClick={(e) => e.stopPropagation()}
            >
              <input
                autoFocus
                className="flex-1 text-xs border rounded px-2 py-1 focus:outline-none focus:ring-1 focus:ring-blue-400"
                value={editValue}
                onChange={(e) => setEditValue(e.target.value)}
                onKeyDown={(e) => {
                  if (e.key === 'Enter') handleSaveOverride()
                  if (e.key === 'Escape') setEditing(false)
                }}
              />
              <button
                onClick={handleSaveOverride}
                className="text-xs px-2 py-1 bg-blue-600 text-white rounded hover:bg-blue-700"
              >
                Save
              </button>
              <button
                onClick={() => setEditing(false)}
                className="text-xs px-2 py-1 bg-gray-200 text-gray-700 rounded hover:bg-gray-300"
              >
                Cancel
              </button>
            </div>
          ) : (
            <p className="text-sm text-gray-800 mt-0.5 truncate">
              {displayValue ?? (
                <span className="text-gray-300 italic">Not extracted</span>
              )}
            </p>
          )}

          {/* Provenance source hint — or explicit "no location" notice */}
          {!editing && (
            entry.provenance ? (
              <p className="text-xs text-gray-400 mt-0.5 truncate">
                {entry.provenance.source_filename} · p.{entry.provenance.location.page} ·{' '}
                <span className="italic">"{entry.provenance.matched_text.slice(0, 60)}{entry.provenance.matched_text.length > 60 ? '…' : ''}"</span>
              </p>
            ) : (
              <p className="text-xs mt-0.5">
                <span className="inline-flex items-center gap-1 px-1.5 py-0.5 rounded bg-gray-100 text-gray-400 font-medium">
                  <span aria-hidden>—</span> No location data
                </span>
              </p>
            )
          )}
        </div>

        {/* Right side: confidence badge + action buttons */}
        <div
          className="flex items-center gap-1 flex-shrink-0"
          onClick={(e) => e.stopPropagation()}
        >
          {entry.provenance && (
            <ConfidenceBadge score={entry.provenance.match_score} />
          )}

          {/* Verify */}
          <button
            title="Mark as verified"
            onClick={() => verifyField(sessionId, entry.fieldPath)}
            className={`w-7 h-7 rounded flex items-center justify-center text-sm transition-colors ${
              isVerified
                ? 'bg-green-500 text-white'
                : 'bg-gray-100 text-gray-500 hover:bg-green-100 hover:text-green-700'
            }`}
          >
            ✓
          </button>

          {/* Edit */}
          <button
            title="Override value"
            onClick={() => {
              setEditValue(displayValue ?? '')
              setEditing(true)
            }}
            className="w-7 h-7 rounded flex items-center justify-center text-sm transition-colors"
            style={{ backgroundColor: '#f3f4f6', color: '#6b7280' }}
            onMouseEnter={e => { (e.currentTarget as HTMLElement).style.backgroundColor = '#eff6ff'; (e.currentTarget as HTMLElement).style.color = '#2563EB' }}
            onMouseLeave={e => { (e.currentTarget as HTMLElement).style.backgroundColor = '#f3f4f6'; (e.currentTarget as HTMLElement).style.color = '#6b7280' }}
          >
            ✎
          </button>

          {/* Flag */}
          <button
            title="Flag for review"
            onClick={() => rejectField(sessionId, entry.fieldPath)}
            className={`w-7 h-7 rounded flex items-center justify-center text-sm transition-colors ${
              isRejected
                ? 'bg-red-500 text-white'
                : 'bg-gray-100 text-gray-500 hover:bg-red-100 hover:text-red-600'
            }`}
          >
            ⚑
          </button>
        </div>
      </div>
    </div>
  )
}

function ConfidenceBadge({ score }: { score: number }) {
  const pct = Math.round(score * 100)
  const [bg, text] =
    pct >= 90
      ? ['bg-green-100 text-green-700', '']
      : pct >= 70
      ? ['bg-yellow-100 text-yellow-700', '']
      : ['bg-red-100 text-red-600', '']

  return (
    <span className={`text-xs font-mono px-1.5 py-0.5 rounded ${bg} ${text}`}>
      {pct}%
    </span>
  )
}

function CheckIcon() {
  return (
    <svg className="w-3 h-3" viewBox="0 0 12 12" fill="currentColor">
      <path d="M10 3L5 8.5 2 5.5" stroke="currentColor" strokeWidth="1.5"
        strokeLinecap="round" strokeLinejoin="round" fill="none" />
    </svg>
  )
}
