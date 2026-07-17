/**
 * FarmManager.jsx
 * Dropdown panel to switch between farms, add new ones,
 * and search locations via OpenStreetMap Nominatim.
 */

import { useState, useEffect, useRef, useCallback } from 'react'
import { searchLocation } from '../services/locationService'

// ── Styles ────────────────────────────────────────────────────────────────────
const s = {
  overlay: {
    position: 'fixed', inset: 0, zIndex: 300,
    background: 'transparent',
  },
  panel: {
    position: 'absolute', top: '100%', right: 0, marginTop: 8,
    width: 360, maxHeight: '80vh', overflowY: 'auto',
    background: '#1e293b', border: '1px solid #334155',
    borderRadius: 14, boxShadow: '0 16px 48px #0009',
    zIndex: 400, padding: 16,
  },
  input: {
    width: '100%', background: '#0f172a', border: '1px solid #334155',
    borderRadius: 8, color: '#f1f5f9', padding: '8px 12px',
    fontSize: 13, outline: 'none', boxSizing: 'border-box',
  },
  btn: (variant = 'primary') => ({
    border: 'none', borderRadius: 8, cursor: 'pointer',
    padding: '7px 14px', fontSize: 13, fontWeight: 600,
    background: variant === 'primary' ? '#1d4ed8'
              : variant === 'danger'  ? '#ef444420'
              : '#334155',
    color: variant === 'danger' ? '#ef4444' : '#fff',
  }),
  farmRow: (active) => ({
    display: 'flex', alignItems: 'center', gap: 10,
    padding: '9px 12px', borderRadius: 10, cursor: 'pointer',
    background: active ? '#1d4ed820' : 'transparent',
    border: `1px solid ${active ? '#1d4ed8' : 'transparent'}`,
    transition: 'background 0.15s',
  }),
  searchResult: {
    padding: '8px 12px', borderRadius: 8, cursor: 'pointer',
    fontSize: 12, color: '#cbd5e1', lineHeight: 1.4,
    transition: 'background 0.1s',
  },
  label: {
    color: '#64748b', fontSize: 11, fontWeight: 600,
    textTransform: 'uppercase', letterSpacing: 0.7,
    marginBottom: 8, display: 'block',
  },
  divider: { borderColor: '#334155', margin: '14px 0' },
}

// ── LocationSearch ────────────────────────────────────────────────────────────
function LocationSearch({ onSelect }) {
  const [query,   setQuery]   = useState('')
  const [results, setResults] = useState([])
  const [loading, setLoading] = useState(false)
  const [error,   setError]   = useState(null)
  const debounceRef           = useRef(null)

  const search = useCallback((q) => {
    clearTimeout(debounceRef.current)
    if (!q.trim()) { setResults([]); return }
    debounceRef.current = setTimeout(async () => {
      setLoading(true); setError(null)
      try {
        const r = await searchLocation(q, 6)
        setResults(r)
      } catch (e) {
        setError('Search failed. Check your connection.')
        setResults([])
      } finally {
        setLoading(false)
      }
    }, 600)  // 600 ms debounce — respects Nominatim 1 req/s policy
  }, [])

  function handleChange(e) {
    const v = e.target.value
    setQuery(v)
    search(v)
  }

  function pick(result) {
    onSelect(result)
    setQuery('')
    setResults([])
  }

  return (
    <div>
      <div style={{ position: 'relative' }}>
        <input
          style={s.input}
          placeholder="Search location (e.g. Kolkata, Punjab, Iowa…)"
          value={query}
          onChange={handleChange}
          autoFocus
          aria-label="Search location"
        />
        {loading && (
          <span style={{ position: 'absolute', right: 10, top: '50%', transform: 'translateY(-50%)', color: '#64748b', fontSize: 12 }}>
            ⏳
          </span>
        )}
      </div>

      {error && <div style={{ color: '#ef4444', fontSize: 12, marginTop: 6 }}>{error}</div>}

      {results.length > 0 && (
        <div style={{ marginTop: 6, border: '1px solid #334155', borderRadius: 10, overflow: 'hidden' }}>
          {results.map(r => (
            <div
              key={r.placeId}
              style={s.searchResult}
              onClick={() => pick(r)}
              onMouseEnter={e => e.currentTarget.style.background = '#0f172a'}
              onMouseLeave={e => e.currentTarget.style.background = 'transparent'}
              role="option"
              aria-selected="false"
            >
              <div style={{ color: '#f1f5f9', fontWeight: 500 }}>{r.shortLabel}</div>
              <div style={{ color: '#475569', fontSize: 11, marginTop: 2 }}>
                {r.label.split(',').slice(2, 4).join(',').trim()} · {r.lat.toFixed(4)}, {r.lon.toFixed(4)}
              </div>
            </div>
          ))}
        </div>
      )}
    </div>
  )
}

// ── AddFarmForm ───────────────────────────────────────────────────────────────
function AddFarmForm({ onAdd, onCancel }) {
  const [name,      setName]      = useState('')
  const [selected,  setSelected]  = useState(null)  // chosen from search
  const [manualLat, setManualLat] = useState('')
  const [manualLon, setManualLon] = useState('')
  const [useManual, setUseManual] = useState(false)

  function handleLocationPick(result) {
    setSelected(result)
    setUseManual(false)
  }

  function handleSubmit(e) {
    e.preventDefault()
    let lat, lon, location
    if (useManual) {
      lat = parseFloat(manualLat)
      lon = parseFloat(manualLon)
      if (isNaN(lat) || isNaN(lon)) return
      location = `${lat.toFixed(4)}, ${lon.toFixed(4)}`
    } else if (selected) {
      lat      = selected.lat
      lon      = selected.lon
      location = selected.shortLabel
    } else return

    onAdd({ name: name.trim() || location, location, lat, lon })
  }

  return (
    <form onSubmit={handleSubmit} style={{ display: 'flex', flexDirection: 'column', gap: 10 }}>
      <input
        style={s.input}
        placeholder="Farm name (optional)"
        value={name}
        onChange={e => setName(e.target.value)}
        aria-label="Farm name"
      />

      {!useManual && <LocationSearch onSelect={handleLocationPick} />}

      {selected && !useManual && (
        <div style={{ background: '#0f172a', borderRadius: 8, padding: '8px 12px', fontSize: 12 }}>
          <div style={{ color: '#22c55e', fontWeight: 600 }}>✓ {selected.shortLabel}</div>
          <div style={{ color: '#64748b', marginTop: 2 }}>{selected.lat.toFixed(5)}, {selected.lon.toFixed(5)}</div>
        </div>
      )}

      <button
        type="button"
        onClick={() => { setUseManual(v => !v); setSelected(null) }}
        style={{ ...s.btn('secondary'), fontSize: 12, padding: '5px 10px', alignSelf: 'flex-start' }}
      >
        {useManual ? '← Use search' : 'Enter coordinates manually'}
      </button>

      {useManual && (
        <div style={{ display: 'flex', gap: 8 }}>
          <input style={{ ...s.input, width: '50%' }} type="number" step="0.0001"
            placeholder="Latitude" value={manualLat} onChange={e => setManualLat(e.target.value)} />
          <input style={{ ...s.input, width: '50%' }} type="number" step="0.0001"
            placeholder="Longitude" value={manualLon} onChange={e => setManualLon(e.target.value)} />
        </div>
      )}

      <div style={{ display: 'flex', gap: 8, justifyContent: 'flex-end', marginTop: 4 }}>
        <button type="button" onClick={onCancel} style={s.btn('secondary')}>Cancel</button>
        <button
          type="submit"
          style={s.btn('primary')}
          disabled={!useManual && !selected}
        >
          Add Farm
        </button>
      </div>
    </form>
  )
}

// ── FarmManager ───────────────────────────────────────────────────────────────
export default function FarmManager({ farms, activeFarm, onSelect, onCreate, onDelete }) {
  const [open,      setOpen]      = useState(false)
  const [addMode,   setAddMode]   = useState(false)
  const containerRef              = useRef(null)

  // Close on outside click
  useEffect(() => {
    if (!open) return
    function handle(e) {
      if (containerRef.current && !containerRef.current.contains(e.target)) {
        setOpen(false)
        setAddMode(false)
      }
    }
    document.addEventListener('mousedown', handle)
    return () => document.removeEventListener('mousedown', handle)
  }, [open])

  function handleAdd(data) {
    onCreate(data)
    setAddMode(false)
    setOpen(false)
  }

  return (
    <div ref={containerRef} style={{ position: 'relative' }}>
      {/* Trigger button */}
      <button
        onClick={() => { setOpen(v => !v); setAddMode(false) }}
        style={{
          display: 'flex', alignItems: 'center', gap: 8,
          background: '#1e293b', border: '1px solid #334155',
          borderRadius: 10, padding: '7px 14px', cursor: 'pointer',
          color: '#f1f5f9', fontSize: 13, fontWeight: 600,
          transition: 'border-color 0.15s',
        }}
        title="Switch farm or add new"
        aria-haspopup="true"
        aria-expanded={open}
      >
        <span style={{ fontSize: 16 }}>🌾</span>
        <span style={{ maxWidth: 140, overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>
          {activeFarm?.name ?? 'Select Farm'}
        </span>
        <span style={{ color: '#64748b', fontSize: 10 }}>{open ? '▲' : '▼'}</span>
      </button>

      {/* Panel */}
      {open && (
        <div style={s.panel}>
          {!addMode ? (
            <>
              <span style={s.label}>Your Farms</span>

              {/* Farm list */}
              <div style={{ display: 'flex', flexDirection: 'column', gap: 6, marginBottom: 14 }}>
                {farms.map(farm => (
                  <div
                    key={farm.id}
                    style={s.farmRow(farm.id === activeFarm?.id)}
                    onClick={() => { onSelect(farm.id); setOpen(false) }}
                    role="button"
                    tabIndex={0}
                    onKeyDown={e => e.key === 'Enter' && onSelect(farm.id)}
                  >
                    <span style={{ fontSize: 20 }}>🌾</span>
                    <div style={{ flex: 1, minWidth: 0 }}>
                      <div style={{ color: '#f1f5f9', fontSize: 13, fontWeight: 600,
                        overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>
                        {farm.name}
                      </div>
                      <div style={{ color: '#64748b', fontSize: 11,
                        overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>
                        📍 {farm.location}
                      </div>
                      <div style={{ color: '#475569', fontSize: 10, marginTop: 1 }}>
                        {farm.lat.toFixed(4)}, {farm.lon.toFixed(4)}
                      </div>
                    </div>
                    {farm.id !== 'default' && farms.length > 1 && (
                      <button
                        onClick={e => { e.stopPropagation(); onDelete(farm.id) }}
                        style={{ ...s.btn('danger'), padding: '3px 8px', fontSize: 12 }}
                        title="Delete farm"
                        aria-label={`Delete ${farm.name}`}
                      >
                        ✕
                      </button>
                    )}
                  </div>
                ))}
              </div>

              <hr style={s.divider} />
              <button
                onClick={() => setAddMode(true)}
                style={{ ...s.btn('primary'), width: '100%', padding: '9px' }}
              >
                + Add New Farm
              </button>
            </>
          ) : (
            <>
              <div style={{ display: 'flex', alignItems: 'center', gap: 10, marginBottom: 14 }}>
                <button
                  onClick={() => setAddMode(false)}
                  style={{ ...s.btn('secondary'), padding: '4px 8px', fontSize: 12 }}
                >
                  ←
                </button>
                <span style={{ color: '#f1f5f9', fontWeight: 600, fontSize: 14 }}>Add New Farm</span>
              </div>
              <AddFarmForm
                onAdd={handleAdd}
                onCancel={() => setAddMode(false)}
              />
            </>
          )}
        </div>
      )}
    </div>
  )
}
