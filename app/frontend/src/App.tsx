import { Navigate, Route, Routes } from 'react-router-dom'
import { TipProvider } from './components/Tip'
import Projects from './pages/Projects'
import Documents from './pages/Documents'
import Scopes from './pages/Scopes'
import Policy from './pages/Policy'
import Level from './pages/Level'

export default function App() {
  return (
    <TipProvider>
      <Routes>
        <Route path="/" element={<Navigate to="/projects" replace />} />
        <Route path="/projects" element={<Projects />} />
        <Route path="/p/:pid/documents" element={<Documents />} />
        <Route path="/p/:pid/scopes" element={<Scopes />} />
        <Route path="/p/:pid/policy" element={<Policy />} />
        <Route path="/p/:pid/level" element={<Level />} />
        <Route path="*" element={<Navigate to="/projects" replace />} />
      </Routes>
    </TipProvider>
  )
}
