import { useState, useEffect, useRef, useCallback } from 'react'
import {
  LineChart, Line, XAxis, YAxis, CartesianGrid, Tooltip, ResponsiveContainer, BarChart, Bar
} from 'recharts'
import {
  Droplets, Thermometer, Wind, Sun, CloudRain, Zap, Activity,
  Leaf, Bug, Timer, Tractor, BarChart2, Settings
} from 'lucide-react'
import './App.css'

const API_BASE = 'https://agromindai-q5m4.onrender.com'
const WS_BASE  = 'wss://agromindai-q5m4.onrender.com'

// ─── Mock / fallback data ──────────────────────────────────────────────────────
const MOCK = {
  soil_moisture: 45, temperature: 28, humidity: 65, light: 2048,
  rain_detected: false, decision: 'DELAY',
  reason: 'Soil moisture adequate. Checking forecast.',
  health_score: 72, next_check_minutes: 15,
}

// ─── Helpers ───────────────────────────────────────────────────────────────────
const soilColor  = v => v < 30 ? '#ef4444' : v < 60 ? '#eab308' : '#22c55e'
const healthColor = s => s < 40 ? '#ef4444' : s < 70 ? '#eab308' : '#22c55e'
const decisionColor = d => d === 'IRRIGATE' ? '#22c55e' : d === 'SKIP' ? '#3b82f6' : '#eab308'
const riskColor  = r => r === 'HIGH' ? '#ef4444' : r === 'MEDIUM' ? '#eab308' : '#22c55e'
const fmt = (val, d=1) => typeof val === 'number' ? val.toFixed(d) : '—'

function toLocalTime(isoStr) {
  if (!isoStr) return '—'
  try {
    // Handle both ISO format and SQLite localtime format
    const d = new Date(isoStr.replace(' ', 'T'))
    if (isNaN(d)) return isoStr
    return d.toLocaleTimeString('en-IN', { hour: '2-digit', minute: '2-digit', second: '2-digit' })
  } catch { return isoStr }
}

function toLocalFull(isoStr) {
  if (!isoStr) return '—'
  try {
    const d = new Date(isoStr.replace(' ', 'T'))
    if (isNaN(d)) return isoStr
    return d.toLocaleString('en-IN', { dateStyle: 'short', timeStyle: 'medium' })
  } catch { return isoStr }
}

// ─── Components ───────────────────────────────────────────────────────────────
function SensorCard({ icon: Icon, label, value, unit, color }) {
  return (
    <div className="sensor-card" style={{ borderColor: color + '44' }}>
      <div className="sensor-icon" style={{ color }}><Icon size={28} /></div>
      <div className="sensor-value" style={{ color }}>{value}<span className="sensor-unit">{unit}</span></div>
      <div className="sensor-label">{label}</div>
    </div>
  )
}

function HealthGauge({ score }) {
  const r = 70, circ = 2 * Math.PI * r
  const progress = (score / 100) * circ
  const color = healthColor(score)
  return (
    <div className="gauge-container">
      <svg width="170" height="170" style={{ transform: 'rotate(-90deg)' }}>
        <circle cx="85" cy="85" r={r} fill="none" stroke="#1e293b" strokeWidth="14"/>
        <circle cx="85" cy="85" r={r} fill="none" stroke={color} strokeWidth="14"
          strokeDasharray={`${progress} ${circ}`} strokeLinecap="round"
          style={{ transition: 'stroke-dasharray 0.8s ease' }}/>
      </svg>
      <div className="gauge-value" style={{ color }}>
        <span style={{ fontSize: '2rem', fontWeight: 700 }}>{Math.round(score)}</span>
        <span style={{ fontSize: '0.9rem', opacity: 0.7 }}>/100</span>
      </div>
    </div>
  )
}

function StressBar({ index, label, color }) {
  const barColor = color === 'green' ? '#22c55e' : color === 'yellow' ? '#eab308' : color === 'orange' ? '#f97316' : '#ef4444'
  return (
    <div style={{ marginBottom: '0.5rem' }}>
      <div style={{ display: 'flex', justifyContent: 'space-between', marginBottom: 4, fontSize: '0.85rem' }}>
        <span style={{ color: '#94a3b8' }}>Crop Stress Index</span>
        <span style={{ color: barColor, fontWeight: 700 }}>{label}</span>
      </div>
      <div style={{ background: '#1e293b', borderRadius: 8, height: 10, overflow: 'hidden' }}>
        <div style={{
          width: `${index}%`, height: '100%',
          background: `linear-gradient(90deg, ${barColor}88, ${barColor})`,
          borderRadius: 8, transition: 'width 1s ease'
        }}/>
      </div>
      <div style={{ textAlign: 'right', fontSize: '0.75rem', color: barColor, marginTop: 2 }}>{index}%</div>
    </div>
  )
}

function AnalyticsPanel({ title, icon: Icon, children, accent = '#6366f1' }) {
  return (
    <div className="analytics-panel" style={{ borderColor: accent + '33' }}>
      <div className="analytics-header" style={{ color: accent }}>
        <Icon size={18} /> <span>{title}</span>
      </div>
      {children}
    </div>
  )
}

// ─── Main App ─────────────────────────────────────────────────────────────────
export default function App() {
  const [data, setData]           = useState(MOCK)
  const [history, setHistory]     = useState([])
  const [analytics, setAnalytics] = useState(null)
  const [online, setOnline]       = useState(false)
  const [lastSeen, setLastSeen]   = useState(null)        // real timestamp
  const [now, setNow]             = useState(new Date())  // live clock
  const [chartTab, setChartTab]   = useState('24h')
  const [cropForm, setCropForm]   = useState({ crop: 'generic', stage: 'vegetative' })
  const [cropSaving, setCropSaving] = useState(false)
  const wsRef = useRef(null)
  const countdown = useRef(null)
  const [remaining, setRemaining] = useState(0)

  // ── Live clock (1-sec tick) ──────────────────────────────────────────────────
  useEffect(() => {
    const id = setInterval(() => setNow(new Date()), 1000)
    return () => clearInterval(id)
  }, [])

  // ── Countdown timer ──────────────────────────────────────────────────────────
  useEffect(() => {
    if (countdown.current) clearInterval(countdown.current)
    if (data.next_check_minutes) {
      setRemaining(data.next_check_minutes * 60)
      countdown.current = setInterval(() => setRemaining(r => Math.max(0, r - 1)), 1000)
    }
    return () => clearInterval(countdown.current)
  }, [data.next_check_minutes])

  const fmtCountdown = s => {
    const m = Math.floor(s / 60), sec = s % 60
    return `${String(m).padStart(2,'0')}:${String(sec).padStart(2,'0')}`
  }

  // ── Fetch history ────────────────────────────────────────────────────────────
  const fetchHistory = useCallback(async () => {
    try {
      const hours = chartTab === '24h' ? 24 : 168
      const r = await fetch(`${API_BASE}/sensor/history?hours=${hours}&limit=200`)
      const rows = await r.json()
      setHistory(rows.reverse().map(row => ({
        time: toLocalTime(row.ts),
        soil: row.soil_moisture,
        temp: row.temperature,
        hum:  row.humidity,
      })))
    } catch {}
  }, [chartTab])

  // ── Fetch analytics ──────────────────────────────────────────────────────────
  const fetchAnalytics = useCallback(async () => {
    try {
      const r = await fetch(`${API_BASE}/analytics/all`)
      const j = await r.json()
      if (!j.error) {
        setAnalytics(j)
        if (j.crop_config) setCropForm({ crop: j.crop_config.crop, stage: j.crop_config.stage })
      }
    } catch {}
  }, [])

  // ── Fetch latest sensor ───────────────────────────────────────────────────────
  const fetchLatest = useCallback(async () => {
    try {
      const r = await fetch(`${API_BASE}/sensor/latest`)
      const j = await r.json()
      if (j.soil_moisture !== undefined) {
        setData(j)
        setOnline(true)
        setLastSeen(j.ts || new Date().toISOString())
      }
    } catch {}
  }, [])

  // ── WebSocket ──────────────────────────────────────────────────────────────────
  useEffect(() => {
    let reconnectTimer
    function connect() {
      const ws = new WebSocket(`${WS_BASE}/ws/dashboard`)
      wsRef.current = ws
      ws.onopen = () => { setOnline(true); console.log('WS connected') }
      ws.onmessage = e => {
        try {
          const msg = JSON.parse(e.data)
          setData(msg)
          setOnline(true)
          setLastSeen(new Date().toISOString())
          fetchAnalytics()
          fetchHistory()
        } catch {}
      }
      ws.onerror = () => setOnline(false)
      ws.onclose = () => {
        setOnline(false)
        reconnectTimer = setTimeout(connect, 5000)
      }
    }
    connect()
    return () => { wsRef.current?.close(); clearTimeout(reconnectTimer) }
  }, [fetchAnalytics, fetchHistory])

  // ── Polling fallback ───────────────────────────────────────────────────────────
  useEffect(() => {
    fetchLatest(); fetchHistory(); fetchAnalytics()
    const id = setInterval(() => { fetchLatest(); fetchAnalytics() }, 30000)
    return () => clearInterval(id)
  }, [fetchLatest, fetchHistory, fetchAnalytics])

  useEffect(() => { fetchHistory() }, [fetchHistory])

  // ── Save crop stage ────────────────────────────────────────────────────────────
  const saveCropStage = async () => {
    setCropSaving(true)
    try {
      await fetch(`${API_BASE}/crop/stage`, {
        method: 'POST', headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(cropForm)
      })
      await fetchAnalytics()
    } finally { setCropSaving(false) }
  }

  // ─── Derived display values ───────────────────────────────────────────────────
  const an = analytics || {}
  const et0     = an.et0 || {}
  const stress  = an.stress || {}
  const pest    = an.pest_risk || {}
  const eta     = an.irrigation_eta || {}
  const water   = an.water_usage || {}
  const crop    = an.crop_config || {}

  const etaHrs  = eta.eta_hours
  const etaDisp = etaHrs == null
    ? (eta.message || 'Calculating…')
    : `~${Math.floor(etaHrs)}h ${Math.round((etaHrs % 1) * 60)}m`

  // ─── Seconds ago ──────────────────────────────────────────────────────────────
  function secondsAgo() {
    if (!lastSeen) return null
    const d = new Date(lastSeen.replace(' ', 'T'))
    if (isNaN(d)) return null
    const s = Math.floor((now - d) / 1000)
    if (s < 60) return `${s}s ago`
    if (s < 3600) return `${Math.floor(s/60)}m ago`
    return `${Math.floor(s/3600)}h ago`
  }

  return (
    <div className="app">
      {/* ─── Header ─────────────────────────────────────────────── */}
      <header className="header">
        <div className="header-left">
          <span className="logo">🌱 AgroMind AI</span>
          <span className={`status-dot ${online ? 'online' : 'offline'}`}/>
          <span className="status-text">{online ? 'System Online' : 'Offline — Mock Data'}</span>
        </div>
        <div className="header-right">
          <span style={{ color: '#64748b', fontSize: '0.8rem' }}>
            {lastSeen ? `Last reading: ${secondsAgo()} · ${toLocalFull(lastSeen)}` : 'Waiting for data…'}
          </span>
          <span className="live-clock">
            {now.toLocaleTimeString('en-IN', { hour: '2-digit', minute: '2-digit', second: '2-digit' })}
          </span>
        </div>
      </header>

      <main className="main">

        {/* ─── Sensor Cards ───────────────────────────────────────── */}
        <section className="section-title">Live Sensor Readings</section>
        <div className="sensor-grid">
          <SensorCard icon={Droplets}   label="Soil Moisture" value={fmt(data.soil_moisture)} unit="%" color={soilColor(data.soil_moisture)} />
          <SensorCard icon={Thermometer} label="Temperature"  value={fmt(data.temperature)}   unit="°C" color="#f97316" />
          <SensorCard icon={Wind}        label="Humidity"     value={fmt(data.humidity)}       unit="%" color="#3b82f6" />
          <SensorCard icon={Sun}         label="Light Level"  value={Math.round(data.light || 0)} unit="" color="#eab308" />
          <SensorCard icon={CloudRain}   label="Rain"         value={data.rain_detected ? 'YES' : 'NO'} unit="" color={data.rain_detected ? '#22c55e' : '#475569'} />
          <SensorCard icon={Zap}         label="Pump"         value={data.pump ? 'ON' : 'OFF'} unit="" color={data.pump ? '#22c55e' : '#475569'} />
        </div>

        {/* ─── Health + Decision ──────────────────────────────────── */}
        <div className="row-two">
          <div className="card health-card">
            <div className="card-title"><Activity size={16}/> Crop Health Score</div>
            <HealthGauge score={data.health_score || 0}/>
          </div>
          <div className="card decision-card">
            <div className="card-title">AI Decision</div>
            <div className="decision-badge" style={{ background: decisionColor(data.decision) + '22', color: decisionColor(data.decision) }}>
              {data.decision || 'SKIP'}
            </div>
            <p className="decision-reason">{data.reason || '—'}</p>
            <div className="next-check">
              <span style={{ color: '#64748b', fontSize: '0.8rem' }}>Next check in</span>
              <span className="countdown" style={{ color: '#22c55e' }}>{fmtCountdown(remaining)}</span>
            </div>
          </div>
        </div>

        {/* ─── Analytics Grid ─────────────────────────────────────── */}
        <section className="section-title">Advanced Analytics</section>
        <div className="analytics-grid">

          {/* ET₀ */}
          <AnalyticsPanel title="ET₀ Drying Rate" icon={Sun} accent="#f97316">
            <div className="ana-main" style={{ color: '#f97316' }}>{fmt(et0.et0_mm_per_day, 2)}<span className="ana-unit"> mm/day</span></div>
            <div className="ana-badge" style={{ color: et0.level === 'High' ? '#ef4444' : et0.level === 'Moderate' ? '#eab308' : '#22c55e' }}>{et0.level || '—'}</div>
            <div className="ana-sub">VPD: {fmt(et0.vpd_kpa, 3)} kPa</div>
          </AnalyticsPanel>

          {/* Crop Stress */}
          <AnalyticsPanel title="Crop Stress Index" icon={Leaf} accent="#22c55e">
            <StressBar index={stress.stress_index || 0} label={stress.label || '—'} color={stress.color || 'green'}/>
            <div style={{ fontSize: '0.75rem', color: '#64748b', marginTop: 4 }}>
              {Object.entries(stress.breakdown || {}).map(([k, v]) =>
                <span key={k} style={{ marginRight: 8 }}>{k}: <b>{v}%</b></span>
              )}
            </div>
          </AnalyticsPanel>

          {/* Pest Risk */}
          <AnalyticsPanel title="Pest & Disease Risk" icon={Bug} accent={riskColor(pest.risk_level)}>
            <div className="ana-badge" style={{ fontSize: '1.4rem', color: riskColor(pest.risk_level), fontWeight: 700 }}>
              {pest.risk_level || '—'}
            </div>
            <div className="ana-sub" style={{ marginTop: 8 }}>{pest.advice || '—'}</div>
          </AnalyticsPanel>

          {/* Irrigation ETA */}
          <AnalyticsPanel title="Next Irrigation ETA" icon={Timer} accent="#6366f1">
            <div className="ana-main" style={{ color: '#6366f1' }}>{etaDisp}</div>
            <div className="ana-sub">Current soil: {fmt(eta.current_soil_pct)}%</div>
            {eta.drying_rate_pct_per_hour && (
              <div className="ana-sub">Drying: {fmt(eta.drying_rate_pct_per_hour, 2)}%/hr</div>
            )}
          </AnalyticsPanel>

          {/* Water Usage */}
          <AnalyticsPanel title="Water Usage" icon={Tractor} accent="#0ea5e9">
            <div style={{ display: 'flex', gap: '1.5rem', marginTop: 8 }}>
              <div>
                <div style={{ color: '#64748b', fontSize: '0.75rem' }}>Today</div>
                <div style={{ color: '#0ea5e9', fontWeight: 700, fontSize: '1.3rem' }}>{water.today?.litres ?? '—'} L</div>
              </div>
              <div>
                <div style={{ color: '#64748b', fontSize: '0.75rem' }}>This Week</div>
                <div style={{ color: '#0ea5e9', fontWeight: 700, fontSize: '1.3rem' }}>{water.this_week?.litres ?? '—'} L</div>
              </div>
            </div>
            <div className="ana-sub">{water.flow_rate_lpm} L/min flow rate assumed</div>
          </AnalyticsPanel>

          {/* Crop Stage */}
          <AnalyticsPanel title="Crop Stage Selector" icon={Settings} accent="#a855f7">
            <div style={{ display: 'flex', gap: '0.5rem', flexWrap: 'wrap', marginTop: 8 }}>
              <select
                value={cropForm.crop}
                onChange={e => setCropForm(f => ({ ...f, crop: e.target.value }))}
                className="crop-select"
              >
                {(crop.available_crops || ['generic','rice','wheat','tomato','potato','maize','sugarcane']).map(c =>
                  <option key={c} value={c}>{c.charAt(0).toUpperCase() + c.slice(1)}</option>
                )}
              </select>
              <select
                value={cropForm.stage}
                onChange={e => setCropForm(f => ({ ...f, stage: e.target.value }))}
                className="crop-select"
              >
                {(crop.available_stages || ['seedling','vegetative','flowering','harvest']).map(s =>
                  <option key={s} value={s}>{s.charAt(0).toUpperCase() + s.slice(1)}</option>
                )}
              </select>
              <button
                onClick={saveCropStage}
                disabled={cropSaving}
                className="crop-save-btn"
              >{cropSaving ? 'Saving…' : 'Apply'}</button>
            </div>
            {crop.soil_min_pct && (
              <div className="ana-sub" style={{ marginTop: 8 }}>
                Target soil: {crop.soil_min_pct}–{crop.soil_max_pct}%
              </div>
            )}
          </AnalyticsPanel>

        </div>

        {/* ─── Historical Chart ────────────────────────────────────── */}
        <section className="section-title" style={{ display: 'flex', alignItems: 'center', gap: '1rem' }}>
          <BarChart2 size={18}/> Historical Trends
          <div className="chart-tabs">
            <button className={`tab-btn ${chartTab === '24h' ? 'active' : ''}`} onClick={() => setChartTab('24h')}>24 Hours</button>
            <button className={`tab-btn ${chartTab === '7d' ? 'active' : ''}`} onClick={() => setChartTab('7d')}>7 Days</button>
          </div>
        </section>
        <div className="card chart-card">
          <ResponsiveContainer width="100%" height={220}>
            <LineChart data={history} margin={{ top: 5, right: 10, left: -20, bottom: 5 }}>
              <CartesianGrid strokeDasharray="3 3" stroke="#1e293b"/>
              <XAxis dataKey="time" tick={{ fill: '#64748b', fontSize: 11 }} interval="preserveStartEnd"/>
              <YAxis tick={{ fill: '#64748b', fontSize: 11 }}/>
              <Tooltip contentStyle={{ background: '#0f172a', border: '1px solid #334155', borderRadius: 8 }}/>
              <Line type="monotone" dataKey="soil" stroke="#22c55e" strokeWidth={2} dot={false} name="Soil %"/>
              <Line type="monotone" dataKey="temp" stroke="#f97316" strokeWidth={2} dot={false} name="Temp °C"/>
              <Line type="monotone" dataKey="hum"  stroke="#3b82f6" strokeWidth={2} dot={false} name="Humidity %"/>
            </LineChart>
          </ResponsiveContainer>
        </div>

      </main>
    </div>
  )
}
