import { useState } from 'react'
import DashboardPage from './pages/DashboardPage'
import HistoryPage from './pages/HistoryPage'

export default function AppShell() {
  const [page, setPage] = useState('dashboard')

  return (
    <div>
      <div style={{ display: 'flex', gap: 8, padding: '16px 20px 0', flexWrap: 'wrap' }}>
        <button onClick={() => setPage('dashboard')} style={{ background: page === 'dashboard' ? '#2563eb' : '#1e293b', color: '#fff', border: 'none', borderRadius: 8, padding: '8px 12px', cursor: 'pointer' }}>
          Dashboard
        </button>
        <button onClick={() => setPage('history')} style={{ background: page === 'history' ? '#2563eb' : '#1e293b', color: '#fff', border: 'none', borderRadius: 8, padding: '8px 12px', cursor: 'pointer' }}>
          History
        </button>
      </div>
      {page === 'dashboard' ? <DashboardPage /> : <HistoryPage />}
    </div>
  )
}
