import { useState, useEffect, useRef, useCallback } from 'react'
import { useFarms } from '../hooks/useFarms'
import {
  LineChart, Line, XAxis, YAxis, CartesianGrid, Tooltip, ResponsiveContainer
} from 'recharts'
import { Droplets, Thermometer, Wind, Sun, CloudRain, Zap } from 'lucide-react'
import WeatherCard from '../components/WeatherCard'
import FarmManager from '../components/FarmManager'
import '../App.css'

const API_BASE = import.meta.env.VITE_API_BASE || 'http://localhost:8000'
const WS_BASE = import.meta.env.VITE_WS_BASE || 'ws://localhost:8000'

const MOCK = {
  soil_moisture: 45,
  temperature: 28,
  humidity: 65,
  light: 2048,
  rain_detected: false,
  decision: 'DELAY',
  reason: 'Soil moisture adequate. Checking forecast.',
  health_score: 72,
  next_check_minutes: 15,
}

function soilColor(v) {
  if (v < 30) return '#ef4444'
  if (v < 60) return '#eab308'
  return '#22c55e'
}
function healthColor(s) {
  if (s < 40) return '#ef4444'
  if (s < 70) return '#eab308'
  return '#22c55e'
}
function decisionColor(d) {
  if (d === 'IRRIGATE') return '#22c55e'
  if (d === 'SKIP') return '#3b82f6'
  return '#eab308'
}
function fmt(val, decimals = 1) {
  return typeof val === 'number' ? val.toFixed(decimals) : '—'
}

function SensorCard({ icon: Icon, label, value, unit, color }) {
  return (
    <div className="sensor-card" style={{ borderColor: color + '44' }}>
      <div className="sensor-icon" style={{ color }}>
        <Icon size={28} />
      </div>
      <div className="sensor-value" style={{ color }}>{value}<span className="sensor-unit">{unit}</span></div>
      <div className="sensor-label">{label}</div>
    </div>
  )
}

function HealthGauge({ score }) {
  const r = 70
  const circ = 2 * Math.PI * r
  const val = Math.min(100, Math.max(0, score || 0))
  const arc = (val / 100) * circ
  const color = healthColor(val)
  return (
    <div className="card" style={{ display: 'flex', flexDirection: 'column', alignItems: 'center', justifyContent: 'center' }}>
      <div className="card-title">Crop Health Score</div>
      <svg width="180" height="180" viewBox="0 0 180 180">
        <circle cx="90" cy="90" r={r} fill="none" stroke="#1e293b" strokeWidth="14" />
        <circle
          cx="90"
          cy="90"
          r={r}
          fill="none"
          stroke={color}
          strokeWidth="14"
          strokeLinecap="round"
          strokeDasharray={`${arc} ${circ}`}
          strokeDashoffset={circ * 0.25}
          style={{ transition: 'stroke-dasharray 0.6s ease, stroke 0.4s ease' }}
        />
        <text x="90" y="85" textAnchor="middle" fill={color} fontSize="32" fontWeight="700">{val}</text>
        <text x="90" y="108" textAnchor="middle" fill="#64748b" fontSize="13">/ 100</text>
      </svg>
      <div style={{ color, fontWeight: 600, fontSize: 14 }}>
        {val >= 70 ? 'Healthy' : val >= 40 ? 'Moderate' : 'Critical'}
      </div>
    </div>
  )
}

function AIDecisionPanel({ decision, reason, nextCheckMinutes, duration, priority, confidence, alerts }) {
  const [seconds, setSeconds] = useState(nextCheckMinutes * 60)
  useEffect(() => {
    setSeconds(nextCheckMinutes * 60)
  }, [nextCheckMinutes])
  useEffect(() => {
    const t = setInterval(() => setSeconds((s) => Math.max(0, s - 1)), 1000)
    return () => clearInterval(t)
  }, [])
  const mm = String(Math.floor(seconds / 60)).padStart(2, '0')
  const ss = String(seconds % 60).padStart(2, '0')
  const color = decisionColor(decision)

  return (
    <div className="card" style={{ flex: 1 }}>
      <div className="card-title">AI Decision</div>
      <div style={{ display: 'flex', alignItems: 'center', gap: 12, marginBottom: 16 }}>
        <span style={{
          background: color + '22', color, border: `1px solid ${color}55`,
          borderRadius: 8, padding: '6px 18px', fontWeight: 700, fontSize: 18, letterSpacing: 1
        }}>{decision || '—'}</span>
        <span style={{ color: '#94a3b8', fontSize: 12, textTransform: 'uppercase' }}>{priority || 'medium'}</span>
      </div>
      <div style={{ color: '#cbd5e1', fontSize: 14, lineHeight: 1.6, marginBottom: 12, minHeight: 40 }}>
        {reason || 'Awaiting sensor data...'}
      </div>
      <div style={{ color: '#f59e0b', fontSize: 13, marginBottom: 10 }}>Duration: {duration ?? 0} min</div>
      <div style={{ color: '#38bdf8', fontSize: 13, marginBottom: 10 }}>Confidence: {confidence || 'medium'}</div>
      {alerts?.length > 0 && (
        <div style={{ color: '#f97316', fontSize: 13, marginBottom: 12 }}>
          Alerts: {alerts.join(', ')}
        </div>
      )}
      <div style={{ borderTop: '1px solid #334155', paddingTop: 16 }}>
        <div style={{ color: '#64748b', fontSize: 12, marginBottom: 4 }}>Next check in</div>
        <div style={{ color: '#22c55e', fontFamily: 'monospace', fontSize: 28, fontWeight: 700 }}>
          {mm}:{ss}
        </div>
      </div>
    </div>
  )
}

function MoistureChart({ history }) {
  const data = history.map((d, i) => ({
    name: d.ts ? d.ts.slice(11, 16) : `#${i + 1}`,
    moisture: d.soil_moisture,
    temp: d.temperature,
  }))

  return (
    <div className="card" style={{ width: '100%' }}>
      <div className="card-title">Soil Moisture History (last 20 readings)</div>
      <ResponsiveContainer width="100%" height={200}>
        <LineChart data={data} margin={{ top: 5, right: 20, left: 0, bottom: 5 }}>
          <CartesianGrid strokeDasharray="3 3" stroke="#1e293b" />
          <XAxis dataKey="name" tick={{ fill: '#64748b', fontSize: 11 }} />
          <YAxis domain={[0, 100]} tick={{ fill: '#64748b', fontSize: 11 }} unit="%" />
          <Tooltip
            contentStyle={{ background: '#1e293b', border: '1px solid #334155', borderRadius: 8, color: '#e2e8f0' }}
            labelStyle={{ color: '#94a3b8' }}
          />
          <Line type="monotone" dataKey="moisture" stroke="#22c55e" strokeWidth={2.5} dot={{ r: 3, fill: '#22c55e' }} activeDot={{ r: 5 }} name="Moisture %" />
          <Line type="monotone" dataKey="temp" stroke="#f97316" strokeWidth={2} dot={false} name="Temp °C" strokeDasharray="4 2" />
        </LineChart>
      </ResponsiveContainer>
      <div style={{ display: 'flex', gap: 20, marginTop: 8 }}>
        <span style={{ color: '#22c55e', fontSize: 12 }}>● Soil Moisture %</span>
        <span style={{ color: '#f97316', fontSize: 12 }}>-- Temperature °C</span>
      </div>
    </div>
  )
}

function PumpControl() {
  const [pumpOn, setPumpOn] = useState(false)
  const [loading, setLoading] = useState(false)

  async function togglePump() {
    setLoading(true)
    const next = !pumpOn
    try {
      await fetch(`${API_BASE}/pump/log`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ action: next ? 'ON' : 'OFF', duration_sec: 0 })
      })
      setPumpOn(next)
    } catch {
      setPumpOn(next)
    } finally {
      setLoading(false)
    }
  }

  return (
    <button
      className="pump-btn"
      onClick={togglePump}
      disabled={loading}
      style={{
        background: pumpOn ? '#22c55e22' : '#ef444422',
        borderColor: pumpOn ? '#22c55e' : '#ef4444',
        color: pumpOn ? '#22c55e' : '#ef4444',
      }}
      title="Toggle irrigation pump"
      id="pump-toggle-btn"
    >
      <Zap size={20} style={{ marginBottom: 2 }} />
      <span style={{ fontSize: 12, fontWeight: 700 }}>PUMP</span>
      <span style={{ fontSize: 11 }}>{pumpOn ? 'ON' : 'OFF'}</span>
    </button>
  )
}

export default function DashboardPage() {
  const [data, setData] = useState(null)
  const [history, setHistory] = useState([])
  const [connected, setConnected] = useState(false)
  const [recommendation, setRecommendation] = useState(null)
  const [farmOptions, setFarmOptions] = useState([])
  const [selectedFarmId, setSelectedFarmId] = useState('green-valley')
  const [analytics, setAnalytics] = useState(null)
  const [loading, setLoading] = useState(true)
  const wsRef = useRef(null)

  const { farms, activeFarm, activeFarmId, selectFarm, createFarm, removeFarm } = useFarms()

  const fetchFarmOptions = useCallback(async () => {
    try {
      const r = await fetch(`${API_BASE}/farms`)
      if (r.ok) {
        const farmsData = await r.json()
        setFarmOptions(farmsData)
        if (!selectedFarmId && farmsData[0]) setSelectedFarmId(farmsData[0].id)
      }
    } catch {}
  }, [selectedFarmId])

  const fetchLatest = useCallback(async () => {
    try {
      const r = await fetch(`${API_BASE}/farms/${selectedFarmId}`)
      if (r.ok) {
        const result = await r.json()
        if (result?.status) {
          setData({
            soil_moisture: result.status.soil_moisture,
            temperature: result.status.temperature,
            humidity: result.status.humidity,
            light: result.status.light_level,
            rain_detected: result.status.rain_probability > 60,
            decision: result.status.recommendation,
            reason: result.status.recommendation_reason,
            health_score: result.status.health_score,
            next_check_minutes: 5,
            pump_status: result.status.pump_status,
            tank_level: result.status.tank_level,
            ...result.status,
          })
          setHistory(result.history || [])
          setRecommendation({
            decision: result.status.recommendation,
            recommended_duration_minutes: result.status.pump_status === 'ON' ? 10 : 0,
            priority: result.status.recommendation === 'IRRIGATE' ? 'high' : 'medium',
            reasons: [result.status.recommendation_reason],
            confidence: 'high',
            alerts: result.status.alerts || [],
          })
          setAnalytics(result.metrics || null)
        }
      }
    } catch {}
  }, [selectedFarmId])

  const fetchHistory = useCallback(async () => {
    try {
      const r = await fetch(`${API_BASE}/sensor/history?limit=20`)
      if (r.ok) {
        const d = await r.json()
        if (Array.isArray(d) && d.length) setHistory(d.slice(0, 20).reverse())
      }
    } catch {}
  }, [])

  const fetchRecommendation = useCallback(async () => {
    try {
      const payload = {
        sensor_data: {
          soil_moisture: data?.soil_moisture ?? MOCK.soil_moisture,
          temperature: data?.temperature ?? MOCK.temperature,
          humidity: data?.humidity ?? MOCK.humidity,
          light: data?.light ?? MOCK.light,
          rain_detected: data?.rain_detected ?? MOCK.rain_detected,
        },
        weather_data: {
          rain_probability_next_hour: data?.rain_probability ?? 10,
          wind_speed: data?.wind_speed ?? 12,
          tank_level: data?.tank_level ?? 80,
        },
      }
      const r = await fetch(`${API_BASE}/irrigation/recommend`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(payload),
      })
      if (r.ok) {
        const result = await r.json()
        setRecommendation(result)
      }
    } catch {
      setRecommendation(null)
    }
  }, [data])

  useEffect(() => {
    function connect() {
      try {
        const ws = new WebSocket(`${WS_BASE}/ws/dashboard`)
        wsRef.current = ws
        ws.onopen = () => setConnected(true)
        ws.onmessage = (e) => { try { const d = JSON.parse(e.data); setData(d) } catch {} }
        ws.onclose = () => { setConnected(false); setTimeout(connect, 3000) }
        ws.onerror = () => ws.close()
      } catch {}
    }
    connect()
    return () => wsRef.current?.close()
  }, [])

  useEffect(() => {
    setLoading(true)
    fetchFarmOptions()
    fetchLatest()
    fetchHistory()
    fetchRecommendation()
    const a = setInterval(fetchLatest, 5000)
    const b = setInterval(fetchHistory, 15000)
    const c = setInterval(fetchRecommendation, 15000)
    return () => { clearInterval(a); clearInterval(b); clearInterval(c) }
  }, [fetchFarmOptions, fetchLatest, fetchHistory, fetchRecommendation])

  useEffect(() => {
    const timer = setTimeout(() => setLoading(false), 400)
    return () => clearTimeout(timer)
  }, [selectedFarmId, data])

  const d = data || MOCK
  const soilC = soilColor(d.soil_moisture)

  return (
    <div className="app-root">
      <header className="header">
        <div className="header-title">
          <span style={{ fontSize: 22 }}>🌱</span>
          <span>AgroMind AI</span>
        </div>
        <div style={{ display: 'flex', alignItems: 'center', gap: 16, flexWrap: 'wrap' }}>
          <select
            value={selectedFarmId}
            onChange={(e) => setSelectedFarmId(e.target.value)}
            style={{ background: '#0f172a', color: '#f8fafc', border: '1px solid #334155', borderRadius: 8, padding: '8px 10px' }}
          >
            {farmOptions.map((farm) => (
              <option key={farm.id} value={farm.id}>{farm.name} · {farm.crop}</option>
            ))}
          </select>
          <FarmManager
            farms={farms}
            activeFarm={activeFarm}
            onSelect={selectFarm}
            onCreate={createFarm}
            onDelete={removeFarm}
          />
          <div className="header-status">
            <span className={`status-dot ${connected ? 'pulse-green' : 'pulse-red'}`} style={{ background: connected ? '#22c55e' : '#ef4444' }} />
            <span style={{ color: connected ? '#22c55e' : '#ef4444', fontWeight: 600 }}>
              {connected ? 'System Online' : 'Offline — Mock Data'}
            </span>
          </div>
        </div>
      </header>

      <main className="main-content">
        {loading ? (
          <div className="card" style={{ padding: 18, marginBottom: 16, color: '#94a3b8' }}>
            Loading farm telemetry…
          </div>
        ) : null}

        <div className="sensor-row" style={{ marginBottom: 12 }}>
          <SensorCard icon={Droplets} label="Avg Soil Moisture" value={analytics ? fmt(analytics.avg_soil_moisture, 0) : fmt(d.soil_moisture, 0)} unit="%" color="#22c55e" />
          <SensorCard icon={Thermometer} label="Avg Temperature" value={analytics ? fmt(analytics.avg_temperature, 1) : fmt(d.temperature)} unit="°C" color="#f97316" />
          <SensorCard icon={Wind} label="Avg Humidity" value={analytics ? fmt(analytics.avg_humidity, 0) : fmt(d.humidity, 0)} unit="%" color="#38bdf8" />
          <SensorCard icon={Zap} label="Latest Recommendation" value={recommendation?.decision || d.decision || '—'} unit="" color="#a78bfa" />
        </div>

        <div className="sensor-row">
          <SensorCard icon={Droplets} label="Soil Moisture" value={fmt(d.soil_moisture, 0)} unit="%" color={soilC} />
          <SensorCard icon={Thermometer} label="Temperature" value={fmt(d.temperature)} unit="°C" color="#f97316" />
          <SensorCard icon={Wind} label="Humidity" value={fmt(d.humidity, 0)} unit="%" color="#38bdf8" />
          <SensorCard icon={Sun} label="Light Level" value={d.light ?? '—'} unit=" lux" color="#facc15" />
          <SensorCard
            icon={d.rain_detected ? CloudRain : Sun}
            label="Rain Status"
            value={d.rain_detected ? 'Rain' : 'Clear'}
            unit=""
            color={d.rain_detected ? '#38bdf8' : '#facc15'}
          />
        </div>

        <div className="middle-row">
          <HealthGauge score={d.health_score} />
          <AIDecisionPanel
            decision={recommendation?.decision || d.decision}
            reason={recommendation?.reasons?.join(' ') || d.reason}
            nextCheckMinutes={d.next_check_minutes ?? 15}
            duration={recommendation?.recommended_duration_minutes ?? 0}
            priority={recommendation?.priority || 'medium'}
            confidence={recommendation?.confidence || 'medium'}
            alerts={recommendation?.alerts || []}
          />
        </div>

        <MoistureChart history={history.length ? history : Array.from({ length: 8 }, (_, i) => ({
          soil_moisture: MOCK.soil_moisture + (Math.random() * 20 - 10),
          temperature: MOCK.temperature + (Math.random() * 4 - 2),
          ts: `2026-03-05T${String(10 + i).padStart(2, '0')}:00`
        }))} />

        <WeatherCard defaultLat={activeFarm.lat} defaultLon={activeFarm.lon} key={activeFarmId} />
      </main>

      <PumpControl />
    </div>
  )
}
