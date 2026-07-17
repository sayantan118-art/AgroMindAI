/**
 * WeatherCard.jsx
 * Full weather display component:
 *   - Current conditions (temp, humidity, wind, UV, rain prob, condition)
 *   - Sunrise / Sunset
 *   - Agricultural alerts
 *   - 24-hour hourly forecast strip
 *   - 7-day forecast table
 *   - Manual location input
 */

import React from 'react'
import { useWeather } from '../hooks/useWeather'

// ── Helpers ───────────────────────────────────────────────────────────────────
function uvLabel(uv) {
  if (uv <= 2)  return { text: 'Low',       color: '#22c55e' }
  if (uv <= 5)  return { text: 'Moderate',  color: '#eab308' }
  if (uv <= 7)  return { text: 'High',      color: '#f97316' }
  if (uv <= 10) return { text: 'Very High', color: '#ef4444' }
  return               { text: 'Extreme',   color: '#a855f7' }
}

function alertColor(type) {
  if (type === 'warning') return { bg: '#ef444418', border: '#ef4444', text: '#fca5a5' }
  if (type === 'caution') return { bg: '#eab30818', border: '#eab308', text: '#fde68a' }
  return                         { bg: '#38bdf818', border: '#38bdf8', text: '#7dd3fc' }
}

// ── Sub-components ────────────────────────────────────────────────────────────
function StatBox({ label, value, unit, sub }) {
  return (
    <div className="weather-stat-box">
      <span style={{ color: '#64748b', fontSize: 11, fontWeight: 600, textTransform: 'uppercase', letterSpacing: 0.6 }}>
        {label}
      </span>
      <span style={{ color: '#f1f5f9', fontSize: 20, fontWeight: 700, lineHeight: 1 }}>
        {value}<span style={{ fontSize: 12, fontWeight: 400, marginLeft: 2, opacity: 0.7 }}>{unit}</span>
      </span>
      {sub && <span style={{ color: '#64748b', fontSize: 11 }}>{sub}</span>}
    </div>
  )
}

function HourlyStrip({ hourly }) {
  return (
    <div className="weather-hourly-strip">
      {hourly.map((h, i) => (
        <div key={i} className="weather-hourly-item">
          <span style={{ color: '#64748b', fontSize: 10 }}>{h.time}</span>
          <span style={{ fontSize: 18 }}>{h.icon}</span>
          <span style={{ color: '#f1f5f9', fontSize: 13, fontWeight: 600 }}>{h.temperature}°</span>
          <span style={{ color: '#38bdf8', fontSize: 10 }}>{h.rainProbability}%</span>
        </div>
      ))}
    </div>
  )
}

function DailyForecast({ daily }) {
  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: 4 }}>
      {daily.map((d, i) => (
        <div key={i} className={`weather-daily-row${i === 0 ? ' today' : ''}`}>
          <span style={{ color: i === 0 ? '#f1f5f9' : '#94a3b8', fontSize: 13, fontWeight: i === 0 ? 600 : 400 }}>
            {i === 0 ? 'Today' : d.date.split(',')[0]}
          </span>
          <span style={{ fontSize: 18, textAlign: 'center' }}>{d.icon}</span>
          <div style={{ display: 'flex', gap: 10, alignItems: 'center' }}>
            <span style={{ color: '#f97316', fontSize: 13, fontWeight: 600 }}>{d.tempMax}°</span>
            <span style={{ color: '#64748b', fontSize: 13 }}>{d.tempMin}°</span>
            {d.rainProbability > 0 && (
              <span style={{ color: '#38bdf8', fontSize: 11 }}>💧{d.rainProbability}%</span>
            )}
          </div>
          <span style={{ color: '#64748b', fontSize: 11, textAlign: 'right' }}>
            💨{d.windMax}
          </span>
        </div>
      ))}
    </div>
  )
}

const btnStyle = {
  background: '#1d4ed8', border: 'none', borderRadius: 8, color: '#fff',
  padding: '6px 14px', fontSize: 13, cursor: 'pointer', fontWeight: 600,
}

// ── Main WeatherCard ──────────────────────────────────────────────────────────
export default function WeatherCard({ defaultLat, defaultLon }) {
  const { weather, loading, error, lat, lon, refresh, setLocation } = useWeather(defaultLat, defaultLon)
  const [showLocation, setShowLocation] = React.useState(false)
  const [draftLat, setDraftLat] = React.useState(lat ?? defaultLat)
  const [draftLon, setDraftLon] = React.useState(lon ?? defaultLon)

  React.useEffect(() => {
    setDraftLat(lat ?? defaultLat)
    setDraftLon(lon ?? defaultLon)
  }, [lat, lon, defaultLat, defaultLon])

  function handleLocationSubmit(e) {
    e.preventDefault()
    const nextLat = Number(draftLat)
    const nextLon = Number(draftLon)
    if (Number.isFinite(nextLat) && Number.isFinite(nextLon)) {
      setLocation(nextLat, nextLon)
      setShowLocation(false)
    }
  }

  // ── Loading ──
  if (loading && !weather) {
    return (
      <div className="card" style={{ display: 'flex', alignItems: 'center', justifyContent: 'center', minHeight: 120 }}>
        <span style={{ color: '#64748b', fontSize: 14 }}>⏳ Fetching weather…</span>
      </div>
    )
  }

  // ── Error ──
  if (error && !weather) {
    return (
      <div className="card">
        <div style={{ color: '#ef4444', fontSize: 14, marginBottom: 12 }}>⚠️ {error}</div>
        <button onClick={refresh} style={btnStyle}>Retry</button>
      </div>
    )
  }

  if (!weather) return null
  const safeWeather = weather || {}
  const current = safeWeather.current || {}
  const hourly24 = Array.isArray(safeWeather.hourly24) ? safeWeather.hourly24 : []
  const daily7 = Array.isArray(safeWeather.daily7) ? safeWeather.daily7 : []
  const alerts = Array.isArray(safeWeather.alerts) ? safeWeather.alerts : []
  const fetchedAt = safeWeather.fetchedAt
  const uv = uvLabel(Number(current.uvIndex) || 0)

  return (
    <div className="card">
      {/* ── Header row ── */}
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start', marginBottom: 16, flexWrap: 'wrap', gap: 8 }}>
        <div>
          <div className="card-title" style={{ marginBottom: 4 }}>Weather Intelligence</div>
          <div style={{ display: 'flex', alignItems: 'center', gap: 12 }}>
            <span style={{ fontSize: 48, lineHeight: 1 }}>{current.icon}</span>
            <div>
              <div style={{ color: '#f1f5f9', fontSize: 36, fontWeight: 700, lineHeight: 1 }}>
                {current.temperature}°C
              </div>
              <div style={{ color: '#94a3b8', fontSize: 13 }}>
                Feels like {current.feelsLike}°C · {current.condition}
              </div>
            </div>
          </div>
        </div>

        {/* Controls */}
        <div style={{ display: 'flex', flexDirection: 'column', alignItems: 'flex-end', gap: 6 }}>
          <div style={{ display: 'flex', gap: 8 }}>
            <button
              onClick={refresh}
              style={{ ...btnStyle, background: '#334155', fontSize: 12, padding: '4px 10px' }}
              title="Refresh weather"
            >
              ↻ Refresh
            </button>
            <button
              onClick={() => setShowLocation(v => !v)}
              style={{ ...btnStyle, background: '#334155', fontSize: 12, padding: '4px 10px' }}
              title="Change location"
            >
              📍 Location
            </button>
          </div>
          {loading && <span style={{ color: '#64748b', fontSize: 11 }}>Updating…</span>}
          {fetchedAt && !loading && (
            <span style={{ color: '#64748b', fontSize: 11 }}>
              Updated {fetchedAt.toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })}
            </span>
          )}
        </div>
      </div>

      {/* ── Location form (collapsible) ── */}
      {showLocation && (
        <form onSubmit={handleLocationSubmit} style={{ marginBottom: 16, padding: 12, background: '#0f172a', borderRadius: 10 }}>
          <div style={{ color: '#94a3b8', fontSize: 12, marginBottom: 8 }}>
            Current: {Number(lat ?? defaultLat).toFixed(4)}, {Number(lon ?? defaultLon).toFixed(4)}
          </div>
          <div style={{ display: 'flex', gap: 8, marginBottom: 8 }}>
            <input
              value={draftLat}
              onChange={(e) => setDraftLat(e.target.value)}
              style={{ flex: 1, background: '#111827', color: '#f8fafc', border: '1px solid #334155', borderRadius: 8, padding: '8px 10px' }}
              placeholder="Latitude"
            />
            <input
              value={draftLon}
              onChange={(e) => setDraftLon(e.target.value)}
              style={{ flex: 1, background: '#111827', color: '#f8fafc', border: '1px solid #334155', borderRadius: 8, padding: '8px 10px' }}
              placeholder="Longitude"
            />
          </div>
          <div style={{ display: 'flex', gap: 8 }}>
            <button type="submit" style={btnStyle}>Apply</button>
            <button type="button" onClick={() => setShowLocation(false)} style={{ ...btnStyle, background: '#334155' }}>Cancel</button>
          </div>
        </form>
      )}

      {/* ── Stats grid ── */}
      <div className="weather-stat-grid" style={{ marginBottom: 16 }}>
        <StatBox label="Humidity"    value={current.humidity}        unit="%" />
        <StatBox label="Wind"        value={current.windSpeed}       unit=" km/h" />
        <StatBox label="Rain Prob."  value={current.rainProbability} unit="%" />
        <StatBox label="UV Index"    value={current.uvIndex}         unit="" sub={uv.text} />
        <StatBox label="Sunrise"     value={current.sunrise}         unit="" />
        <StatBox label="Sunset"      value={current.sunset}          unit="" />
      </div>

      {/* ── Agricultural alerts ── */}
      {alerts.length > 0 && (
        <div style={{ display: 'flex', flexDirection: 'column', gap: 8, marginBottom: 16 }}>
          {alerts.map((a, i) => {
            const c = alertColor(a.type)
            return (
              <div key={i} className="weather-alert" style={{
                background: c.bg,
                border: `1px solid ${c.border}44`,
                borderLeft: `3px solid ${c.border}`,
              }}>
                <span style={{ fontSize: 18 }}>{a.icon}</span>
                <span style={{ color: c.text, fontSize: 13, lineHeight: 1.5 }}>{a.message}</span>
              </div>
            )
          })}
        </div>
      )}

      {/* ── 24-hour forecast ── */}
      <div style={{ marginBottom: 16 }}>
        <div style={{ color: '#64748b', fontSize: 11, fontWeight: 600, textTransform: 'uppercase', letterSpacing: 0.8, marginBottom: 8 }}>
          Next 24 Hours
        </div>
        <HourlyStrip hourly={hourly24} />
      </div>

      {/* ── 7-day forecast ── */}
      <div>
        <div style={{ color: '#64748b', fontSize: 11, fontWeight: 600, textTransform: 'uppercase', letterSpacing: 0.8, marginBottom: 8 }}>
          7-Day Forecast
        </div>
        <DailyForecast daily={daily7} />
      </div>
    </div>
  )
}
