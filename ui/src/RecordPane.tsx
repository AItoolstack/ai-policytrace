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

  return (
    <div className="flex flex-col h-full">
      {/* Header */}
      <div className="px-5 py-4 border-b flex-shrink-0" style={{ backgroundColor: '#1F2937' }}>
        <h2 className="text-sm font-semibold text-white">Golden Record</h2>
        <p className="text-xs mt-0.5" style={{ color: 'rgba(255,255,255,0.5)' }}>
          Click any field to highlight its source location in the PDF.
        </p>
      </div>

      {/* Scrollable field list */}
      <div className="flex-1 overflow-y-auto px-4 py-3 space-y-5">
        {fieldsBySection.map(({ section, entries }) => (
          <section key={section}>
            <h3 className="text-xs font-semibold uppercase tracking-wider mb-2 px-1" style={{ color: '#008080' }}>
              {SECTION_LABELS[section] ?? section}
            </h3>
            <div className="space-y-1">
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
        label: formatLabel(key),
        value: String(val),
        section: pathPrefix.split('.')[0],
        provenance: provenanceMap[path],
      })
    }
  }
}

function formatLabel(key: string): string {
  return key
    .replace(/_/g, ' ')
    .replace(/\b\w/g, (c) => c.toUpperCase())
}
