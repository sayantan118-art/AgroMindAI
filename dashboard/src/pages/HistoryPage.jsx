import { useEffect, useMemo, useState } from 'react'

const API_BASE = import.meta.env.VITE_API_BASE || 'http://localhost:8000'

function fmt(value, decimals = 1) {
  return typeof value === 'number' ? value.toFixed(decimals) : '—'
}

export default function HistoryPage() {
  const [rows, setRows] = useState([])
  const [loading, setLoading] = useState(true)
  const [filter, setFilter] = useState('all')

  useEffect(() => {
    let mounted = true
    async function loadHistory() {
      try {
        const res = await fetch(`${API_BASE}/sensor/history?limit=100`)
        if (!res.ok) throw new Error('Failed to load history')
        const data = await res.json()
        if (mounted) setRows(Array.isArray(data) ? data : [])
      } catch {
        if (mounted) setRows([])
      } finally {
        if (mounted) setLoading(false)
      }
    }

    loadHistory()
    return () => { mounted = false }
  }, [])

  const filteredRows = useMemo(() => {
    if (!filter || filter === 'all') return rows
    return rows.filter((row) => (row.decision || '').toLowerCase() === filter)
  }, [rows, filter])

  return (
    <div className="app-root">
      <header className="header">
        <div className="header-title">
          <span style={{ fontSize: 22 }}>📜</span>
          <span>History</span>
        </div>
        <div style={{ display: 'flex', gap: 12, alignItems: 'center' }}>
          <select
            value={filter}
            onChange={(e) => setFilter(e.target.value)}
            style={{ background: '#0f172a', color: '#f8fafc', border: '1px solid #334155', borderRadius: 8, padding: '8px 10px' }}
          >
            <option value="all">All decisions</option>
            <option value="irrigate">Irrigate</option>
            <option value="delay">Delay</option>
            <option value="skip">Skip</option>
          </select>
        </div>
      </header>

      <main className="main-content">
        <div className="card" style={{ padding: 18 }}>
          <div style={{ color: '#94a3b8', marginBottom: 12 }}>
            Historical sensor and irrigation readings from the backend.
          </div>
          {loading ? (
            <div style={{ color: '#64748b' }}>Loading history…</div>
          ) : filteredRows.length === 0 ? (
            <div style={{ color: '#64748b' }}>No history available yet.</div>
          ) : (
            <div style={{ overflowX: 'auto' }}>
              <table style={{ width: '100%', borderCollapse: 'collapse', color: '#e2e8f0' }}>
                <thead>
                  <tr style={{ textAlign: 'left', borderBottom: '1px solid #334155' }}>
                    <th style={{ padding: '10px 8px' }}>Time</th>
                    <th style={{ padding: '10px 8px' }}>Soil</th>
                    <th style={{ padding: '10px 8px' }}>Temp</th>
                    <th style={{ padding: '10px 8px' }}>Humidity</th>
                    <th style={{ padding: '10px 8px' }}>Decision</th>
                    <th style={{ padding: '10px 8px' }}>Confidence</th>
                  </tr>
                </thead>
                <tbody>
                  {filteredRows.map((row, idx) => (
                    <tr key={row.id ?? idx} style={{ borderBottom: '1px solid #1e293b' }}>
                      <td style={{ padding: '10px 8px', color: '#94a3b8' }}>{row.ts || '—'}</td>
                      <td style={{ padding: '10px 8px' }}>{fmt(row.soil_moisture, 0)}%</td>
                      <td style={{ padding: '10px 8px' }}>{fmt(row.temperature, 1)}°C</td>
                      <td style={{ padding: '10px 8px' }}>{fmt(row.humidity, 0)}%</td>
                      <td style={{ padding: '10px 8px' }}>{row.decision || '—'}</td>
                      <td style={{ padding: '10px 8px' }}>{fmt(row.confidence, 2)}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}
        </div>
      </main>
    </div>
  )
}
