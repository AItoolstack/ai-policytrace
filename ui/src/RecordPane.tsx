import { useMemo } from 'react'
import type { FieldEntry, GoldenRecord } from './types'
import { useStore } from './store'
import { FieldRow } from './FieldRow'

interface Props {
  sessionId: string
}

const SECTION_LABELS: Record<string, string> = {
  policy_header: 'Policy Header',
  vehicle_details: 'Vehicle Details',
  driver_details: 'Drivers',
  cover_and_excesses: 'Cover & Excesses',
  financial_summary: 'Financial Summary',
  additional_risk_data: 'Additional Risk Data',
}

export function RecordPane({ sessionId }: Props) {
  const sessionData = useStore((s) => s.sessionData)
  const reviewState = useStore((s) => s.reviewState)
  const activeFieldPath = useStore((s) => s.activeFieldPath)
  const setActiveField = useStore((s) => s.setActiveField)

  const fieldsBySection = useMemo(() => {
    if (!sessionData) return []
    return flattenRecord(sessionData.record, sessionData.provenance.reduce(
      (acc, p) => { acc[p.field_path] = p; return acc },
      {} as Record<string, import('./types').FieldProvenance>,
    ))
  }, [sessionData])

  if (!sessionData) return null

  const conflicts = sessionData.conflicts ?? []

  return (
    <div className="flex flex-col h-full bg-paper">
      {/* Header */}
      <div className="px-5 h-[52px] flex items-center justify-between gap-3 border-b border-ink-700 bg-ink-800 flex-shrink-0">
        <div className="min-w-0">
          <h2 className="text-[14px] font-semibold text-ink-100 tracking-[-0.01em]">Golden Record</h2>
        </div>
        <p className="text-[12px] text-ink-400 truncate">Select a field to see its source in the PDF</p>
      </div>

      {/* Scrollable field list */}
      <div className="flex-1 overflow-y-auto scroll-paper px-4 sm:px-5 py-5 space-y-7">
        {conflicts.length > 0 && (
          <section aria-label="Cross-document conflicts" className="rounded-xl border border-signal/50 bg-signal-tint px-4 py-3.5">
            <p className="eyebrow text-signal-deep">
              {conflicts.length} cross-document conflict{conflicts.length > 1 ? 's' : ''} · resolved by authority rules
            </p>
            <ul className="mt-2 space-y-2">
              {conflicts.map((c) => (
                <li key={c.field} className="text-[13px] text-paper-ink">
                  <span className="font-mono text-[12px] text-paper-muted">{c.field}</span>
                  <span className="block mt-0.5">
                    Winner: <span className="font-semibold capitalize">{c.winner}</span>
                  </span>
                  <span className="block mt-0.5 text-[12px] text-paper-muted">
                    Schedule: <span className="text-paper-ink">{c.schedule_value ?? '—'}</span>
                    {' · '}Certificate: <span className="text-paper-ink">{c.certificate_value ?? '—'}</span>
                  </span>
                </li>
              ))}
            </ul>
          </section>
        )}

        {fieldsBySection.map(({ section, entries }) => (
          <section key={section}>
            <div className="flex items-baseline justify-between mb-2.5 px-1">
              <h3 className="eyebrow text-signal-deep">{SECTION_LABELS[section] ?? section}</h3>
              <span className="font-mono text-[11px] text-paper-muted">
                {entries.filter((e) => e.provenance).length}/{entries.length} located
              </span>
            </div>
            <div className="space-y-1.5">
              {entries.map((entry) => (
                <FieldRow
                  key={entry.fieldPath}
                  entry={entry}
                  sessionId={sessionId}
                  isActive={activeFieldPath === entry.fieldPath}
                  review={reviewState[entry.fieldPath]}
                  onClick={() =>
                    setActiveField(activeFieldPath === entry.fieldPath ? null : entry)
                  }
                />
              ))}
            </div>
          </section>
        ))}
      </div>
    </div>
  )
}

// ── Field flattening helpers ───────────────────────────────────────────────

interface SectionGroup {
  section: string
  entries: FieldEntry[]
}

function flattenRecord(
  record: GoldenRecord,
  provenanceMap: Record<string, import('./types').FieldProvenance>,
): SectionGroup[] {
  const groups: SectionGroup[] = []

  for (const [sectionKey, sectionValue] of Object.entries(record)) {
    if (sectionValue == null) continue

    const entries: FieldEntry[] = []

    if (Array.isArray(sectionValue)) {
      // driver_details
      sectionValue.forEach((item: Record<string, unknown>, idx: number) => {
        walkObject(
          item,
          `${sectionKey}[${idx}]`,
          `Driver ${idx + 1}`,
          entries,
          provenanceMap,
        )
      })
    } else if (typeof sectionValue === 'object') {
      walkObject(
        sectionValue as Record<string, unknown>,
        sectionKey,
        '',
        entries,
        provenanceMap,
      )
    } else {
      entries.push({
        fieldPath: sectionKey,
        label: formatLabel(sectionKey),
        value: String(sectionValue),
        section: sectionKey,
        provenance: provenanceMap[sectionKey],
      })
    }

    if (entries.length > 0) {
      groups.push({ section: sectionKey, entries })
    }
  }

  return groups
}

function walkObject(
  obj: Record<string, unknown>,
  pathPrefix: string,
  _labelPrefix: string,
  out: FieldEntry[],
  provenanceMap: Record<string, import('./types').FieldProvenance>,
) {
  for (const [key, val] of Object.entries(obj)) {
    const path = `${pathPrefix}.${key}`

    if (val == null) continue

    if (typeof val === 'object' && !Array.isArray(val)) {
      walkObject(val as Record<string, unknown>, path, key, out, provenanceMap)
    } else if (Array.isArray(val)) {
      val.forEach((item, i) => {
        if (item == null) return
        const iPath = `${path}[${i}]`
        if (typeof item === 'object') {
          walkObject(item as Record<string, unknown>, iPath, key, out, provenanceMap)
        } else {
          out.push({
            fieldPath: iPath,
            label: `${formatLabel(key)} [${i}]`,
            value: String(item),
            section: pathPrefix.split('.')[0],
            provenance: provenanceMap[iPath],
          })
        }
      })
    } else {
      out.push({
        fieldPath: path,
        label: driverPrefix(pathPrefix) + formatLabel(key),
        value: String(val),
        section: pathPrefix.split('.')[0],
        provenance: provenanceMap[path],
      })
    }
  }
}

const LABELS: Record<string, string> = {
  vrm: 'Registration (VRM)',
  dob: 'Date of Birth',
  license_type: 'Licence Type',
  is_main_driver: 'Main Driver',
  has_security_device: 'Security Device',
  overnight_postcode: 'Overnight Postcode',
  standard_compulsory: 'Compulsory Excess',
  total_accidental_damage: 'Accidental Damage Excess',
  own_repairer_additional_excess: 'Own Repairer Excess',
  years: 'NCD Years',
  protected: 'NCD Protected',
}

function formatLabel(key: string): string {
  return LABELS[key] ?? key
    .replace(/_/g, ' ')
    .replace(/\b\w/g, (c) => c.toUpperCase())
}

function driverPrefix(pathPrefix: string): string {
  const m = pathPrefix.match(/^driver_details\[(\d+)\]$/)
  return m ? `Driver ${Number(m[1]) + 1} · ` : ''
}
