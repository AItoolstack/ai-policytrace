import { useCallback, useEffect, useMemo, useRef, useState } from 'react'
import { Document, Page } from 'react-pdf'
import type { FieldProvenance } from './types'
import { useStore } from './store'
import { api } from './api'

interface Props {
  sessionId: string
}

export function PDFPane({ sessionId }: Props) {
  const sessionData = useStore((s) => s.sessionData)
  const activePdfFile = useStore((s) => s.activePdfFile)
  const activeProvenance = useStore((s) => s.activeProvenance)
  const setActivePdf = useStore((s) => s.setActivePdf)

  const [numPages, setNumPages] = useState(0)
  const [renderedPages, setRenderedPages] = useState<Set<number>>(new Set())
  const [containerWidth, setContainerWidth] = useState(600)
  const containerRef = useRef<HTMLDivElement>(null)
  const pageRefs = useRef<Map<number, HTMLDivElement>>(new Map())

  // Track which PDF URL we last requested a scroll for, to avoid re-firing
  const pendingScrollRef = useRef<{ page: number; pdfFile: string } | null>(null)

  // Unique PDF filenames from provenance
  const pdfFiles = useMemo(() => {
    const seen = new Set<string>()
    return (sessionData?.provenance ?? [])
      .map((p) => p.source_filename)
      .filter((f) => { const fresh = !seen.has(f); seen.add(f); return fresh })
  }, [sessionData?.provenance])

  // Set container width on resize
  useEffect(() => {
    const el = containerRef.current
    if (!el) return
    const obs = new ResizeObserver(([entry]) => {
      setContainerWidth(Math.floor(entry.contentRect.width) - 24)
    })
    obs.observe(el)
    setContainerWidth(Math.floor(el.clientWidth) - 24)
    return () => obs.disconnect()
  }, [])

  // When active provenance changes: enqueue a scroll request
  useEffect(() => {
    if (!activeProvenance) return
    pendingScrollRef.current = {
      page: activeProvenance.location.page,
      pdfFile: activeProvenance.source_filename,
    }
    // Reset rendered-pages set when switching documents
    if (activeProvenance.source_filename !== activePdfFile) {
      setRenderedPages(new Set())
    }
    // Try immediately (page already rendered)
    tryScroll()
  }, [activeProvenance]) // eslint-disable-line react-hooks/exhaustive-deps

  // When a page finishes rendering, check if a scroll is pending for it
  const handlePageRenderSuccess = useCallback((pageNum: number) => {
    setRenderedPages((prev) => new Set([...prev, pageNum]))
    const pending = pendingScrollRef.current
    if (pending && pending.page === pageNum && pending.pdfFile === activePdfFile) {
      const el = pageRefs.current.get(pageNum)
      el?.scrollIntoView({ behavior: 'smooth', block: 'center' })
      pendingScrollRef.current = null
    }
  }, [activePdfFile])

  function tryScroll() {
    const pending = pendingScrollRef.current
    if (!pending) return
    if (pending.pdfFile !== activePdfFile) return
    const el = pageRefs.current.get(pending.page)
    if (el) {
      el.scrollIntoView({ behavior: 'smooth', block: 'center' })
      pendingScrollRef.current = null
    }
  }

  // Reset rendered pages when the PDF URL changes
  const pdfUrl = activePdfFile ? api.pdfUrl(sessionId, activePdfFile) : null
  const prevPdfUrlRef = useRef<string | null>(null)
  if (pdfUrl !== prevPdfUrlRef.current) {
    prevPdfUrlRef.current = pdfUrl
    // Clear page refs — old page elements are stale after document switch
    pageRefs.current.clear()
  }

  // Highlights for the currently displayed PDF
  const highlights = useMemo((): FieldProvenance[] => {
    if (!sessionData || !activePdfFile) return []
    return sessionData.provenance.filter(
      (p) => p.source_filename === activePdfFile,
    )
  }, [sessionData, activePdfFile])

  return (
    <div className="flex flex-col h-full">
      {/* PDF file selector */}
      {pdfFiles.length > 1 && (
        <div className="flex flex-wrap gap-2 p-3 border-b flex-shrink-0" style={{ backgroundColor: '#1F2937' }}>
          {pdfFiles.map((f) => (
            <button
              key={f}
              onClick={() => setActivePdf(f)}
              className="px-3 py-1 rounded text-xs font-medium transition-colors"
              style={activePdfFile === f
                ? { backgroundColor: '#008080', color: '#ffffff' }
                : { backgroundColor: 'rgba(255,255,255,0.08)', border: '1px solid rgba(255,255,255,0.15)', color: 'rgba(255,255,255,0.7)' }
              }
            >
              {f}
            </button>
          ))}
        </div>
      )}

      {/* PDF scroll area */}
      <div
        ref={containerRef}
        className="flex-1 overflow-y-auto pdf-scroll-container bg-gray-200 p-3 space-y-4"
      >
        {pdfUrl ? (
          <Document
            file={pdfUrl}
            onLoadSuccess={({ numPages: n }) => {
              setNumPages(n)
              setRenderedPages(new Set())
            }}
            loading={<LoadingPlaceholder />}
            error={<ErrorPlaceholder />}
          >
            {Array.from({ length: numPages }, (_, i) => i + 1).map((pageNum) => {
              const pageHighlights = highlights.filter(
                (h) => h.location.page === pageNum,
              )
              const hasActive =
                activeProvenance?.location.page === pageNum &&
                activeProvenance.source_filename === activePdfFile

              return (
                <div
                  key={pageNum}
                  ref={(el) => {
                    if (el) pageRefs.current.set(pageNum, el)
                    else pageRefs.current.delete(pageNum)
                  }}
                  // Use block + explicit width so the overlay div always matches
                  // the canvas dimensions exactly (inline-block can shrink-wrap)
                  style={{ position: 'relative', width: containerWidth }}
                  className={`rounded shadow-md transition-shadow overflow-hidden ${
                    hasActive ? 'ring-4 ring-blue-500' : ''
                  }`}
                >
                  <Page
                    pageNumber={pageNum}
                    width={containerWidth}
                    renderTextLayer={false}
                    renderAnnotationLayer={false}
                    onRenderSuccess={() => handlePageRenderSuccess(pageNum)}
                  />

                  {/* Highlight overlay — percentage-based, top-left origin */}
                  <div
                    style={{ position: 'absolute', inset: 0, pointerEvents: 'none' }}
                    aria-hidden
                  >
                    {pageHighlights.map((h) => {
                      const [x0, y0, x1, y1] = h.location.bbox
                      const isActive = activeProvenance?.field_path === h.field_path
                      return (
                        <div
                          key={h.field_path}
                          style={{
                            position: 'absolute',
                            left: `${x0}%`,
                            top: `${y0}%`,
                            width: `${x1 - x0}%`,
                            height: `${y1 - y0}%`,
                            background: isActive
                              ? 'rgba(59, 130, 246, 0.35)'   /* blue-500 fill */
                              : 'rgba(134, 239, 172, 0.35)', /* green-300 fill */
                            border: isActive
                              ? '3px solid rgba(37, 99, 235, 1)'   /* blue-700 solid */
                              : '2px solid rgba(22, 163, 74, 0.9)', /* green-600 */
                            borderRadius: 3,
                            boxShadow: isActive
                              ? '0 0 0 2px rgba(147, 197, 253, 0.6)' /* blue glow */
                              : 'none',
                            transition: 'background 0.15s, border 0.15s',
                          }}
                          title={`${h.field_path}: ${h.extracted_value}`}
                        />
                      )
                    })}
                  </div>
                </div>
              )
            })}
          </Document>
        ) : (
          <div className="flex items-center justify-center h-full text-gray-400 text-sm">
            No PDF selected
          </div>
        )}
      </div>
    </div>
  )
}

function LoadingPlaceholder() {
  return (
    <div className="flex items-center justify-center p-12 text-gray-400 text-sm">
      Loading PDF…
    </div>
  )
}

function ErrorPlaceholder() {
  return (
    <div className="flex items-center justify-center p-12 text-red-400 text-sm">
      Failed to load PDF.
    </div>
  )
}

