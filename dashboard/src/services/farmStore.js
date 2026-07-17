/**
 * farmStore.js
 * Persists farm list and active farm in localStorage.
 * No external dependencies.
 *
 * Farm shape:
 * {
 *   id:        string  (uuid-ish)
 *   name:      string
 *   location:  string  (human-readable)
 *   lat:       number
 *   lon:       number
 *   createdAt: string  (ISO)
 * }
 */

const FARMS_KEY  = 'agromind_farms'
const ACTIVE_KEY = 'agromind_active_farm'

function generateId() {
  return `farm_${Date.now()}_${Math.random().toString(36).slice(2, 7)}`
}

export function loadFarms() {
  try {
    return JSON.parse(localStorage.getItem(FARMS_KEY) ?? '[]')
  } catch {
    return []
  }
}

export function saveFarms(farms) {
  localStorage.setItem(FARMS_KEY, JSON.stringify(farms))
}

export function loadActiveFarmId() {
  return localStorage.getItem(ACTIVE_KEY) ?? null
}

export function saveActiveFarmId(id) {
  if (id) localStorage.setItem(ACTIVE_KEY, id)
  else    localStorage.removeItem(ACTIVE_KEY)
}

export function addFarm({ name, location, lat, lon }) {
  const farms = loadFarms()
  const farm  = { id: generateId(), name, location, lat, lon, createdAt: new Date().toISOString() }
  const updated = [...farms, farm]
  saveFarms(updated)
  return { farm, farms: updated }
}

export function updateFarm(id, patch) {
  const farms   = loadFarms()
  const updated = farms.map(f => f.id === id ? { ...f, ...patch } : f)
  saveFarms(updated)
  return updated
}

export function deleteFarm(id) {
  const updated = loadFarms().filter(f => f.id !== id)
  saveFarms(updated)
  // If we deleted the active farm, clear the selection
  if (loadActiveFarmId() === id) saveActiveFarmId(null)
  return updated
}
