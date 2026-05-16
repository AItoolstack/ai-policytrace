import { create } from 'zustand'
import { api } from './api'
import type { FieldEntry, FieldProvenance, ReviewAction, ReviewState, SessionData } from './types'

interface AppState {
  // Session data
  sessionData: SessionData | null
  reviewState: ReviewState

  // UI state
  activePdfFile: string | null        // filename of the PDF currently displayed
  activeFieldPath: string | null      // field path the user clicked
  activeProvenance: FieldProvenance | null

  // Actions
  setSession: (data: SessionData) => void
  loadReviewState: (sessionId: string) => Promise<void>
  setActiveField: (entry: FieldEntry | null) => void
  verifyField: (sessionId: string, fieldPath: string) => Promise<void>
  overrideField: (sessionId: string, fieldPath: string, newValue: string) => Promise<void>
  rejectField: (sessionId: string, fieldPath: string) => Promise<void>
  setActivePdf: (filename: string) => void
}

export const useStore = create<AppState>((set, get) => ({
  sessionData: null,
  reviewState: {},
  activePdfFile: null,
  activeFieldPath: null,
  activeProvenance: null,

  setSession(data) {
    // Set default active PDF to the first source file found in provenance
    const firstPdf = data.provenance[0]?.source_filename ?? null
    set({ sessionData: data, activePdfFile: firstPdf })
  },

  async loadReviewState(sessionId) {
    const state = await api.getReviewState(sessionId)
    set({ reviewState: state })
  },

  setActiveField(entry) {
    if (!entry) {
      set({ activeFieldPath: null, activeProvenance: null })
      return
    }
    const { sessionData } = get()
    const provenance = sessionData?.provenance.find(
      (p) => p.field_path === entry.fieldPath,
    ) ?? null

    set({
      activeFieldPath: entry.fieldPath,
      activeProvenance: provenance,
      // Switch PDF pane to the file that contains this field
      activePdfFile: provenance?.source_filename ?? get().activePdfFile,
    })
  },

  async verifyField(sessionId, fieldPath) {
    await _applyReview(sessionId, fieldPath, 'verify', undefined, set)
  },

  async overrideField(sessionId, fieldPath, newValue) {
    await _applyReview(sessionId, fieldPath, 'override', newValue, set)
  },

  async rejectField(sessionId, fieldPath) {
    await _applyReview(sessionId, fieldPath, 'reject', undefined, set)
  },

  setActivePdf(filename) {
    set({ activePdfFile: filename })
  },
}))

async function _applyReview(
  sessionId: string,
  fieldPath: string,
  action: ReviewAction,
  overriddenValue: string | undefined,
  set: (partial: Partial<AppState>) => void,
) {
  await api.updateReview(sessionId, fieldPath, action, overriddenValue)
  const fresh = await api.getReviewState(sessionId)
  set({ reviewState: fresh })
}
