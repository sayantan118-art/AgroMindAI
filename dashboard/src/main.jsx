import { StrictMode } from 'react'
import { createRoot } from 'react-dom/client'
import './index.css'
import AppShell from './AppShell.jsx'
import ErrorBoundary from './components/ErrorBoundary.jsx'

createRoot(document.getElementById('root')).render(
  <StrictMode>
    <ErrorBoundary>
      <AppShell />
    </ErrorBoundary>
  </StrictMode>,
)
