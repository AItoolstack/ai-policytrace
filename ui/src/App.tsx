import { Route, Routes } from 'react-router-dom'
import { UploadPage } from './UploadPage'
import { SessionPage } from './SessionPage'

export default function App() {
  return (
    <Routes>
      <Route path="/" element={<UploadPage />} />
      <Route path="/session/:sessionId" element={<SessionPage />} />
      {/* Catch-all: redirect unknown paths to upload */}
      <Route path="*" element={<UploadPage />} />
    </Routes>
  )
}


