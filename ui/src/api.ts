import axios from 'axios'
import type { ProcessResponse, ReviewAction, ReviewState, SessionData } from './types'

const http = axios.create({ baseURL: '/' })

export const api = {
  async processDocuments(files: File[]): Promise<ProcessResponse> {
    const form = new FormData()
    for (const f of files) form.append('files', f)
    const { data } = await http.post<ProcessResponse>('/api/process', form, {
      headers: { 'Content-Type': 'multipart/form-data' },
    })
    return data
  },

  async getSession(sessionId: string): Promise<SessionData> {
    const { data } = await http.get<SessionData>(`/api/session/${sessionId}`)
    return data
  },

  async getReviewState(sessionId: string): Promise<ReviewState> {
    const { data } = await http.get<ReviewState>(`/api/session/${sessionId}/review-state`)
    return data
  },

  async updateReview(
    sessionId: string,
    fieldPath: string,
    action: ReviewAction,
    overriddenValue?: string,
  ): Promise<void> {
    await http.patch(`/api/session/${sessionId}/review`, {
      field_path: fieldPath,
      action,
      overridden_value: overriddenValue ?? null,
    })
  },

  /** URL to stream a PDF — used directly by the PDF viewer component */
  pdfUrl(sessionId: string, filename: string): string {
    return `/api/pdf/${sessionId}/${encodeURIComponent(filename)}`
  },
}
