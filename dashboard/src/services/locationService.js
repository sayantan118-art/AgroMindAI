/**
 * locationService.js
 * Uses OpenStreetMap Nominatim API — free, no API key.
 * Rate limit: 1 request/second (we debounce in the hook).
 */

const NOMINATIM = 'https://nominatim.openstreetmap.org/search'

/**
 * Search for a place by name.
 * Returns up to `limit` results with label, lat, lon.
 *
 * @param {string} query
 * @param {number} limit
 * @returns {Promise<Array<{label: string, lat: number, lon: number, placeId: number}>>}
 */
export async function searchLocation(query, limit = 6) {
  if (!query.trim()) return []

  const params = new URLSearchParams({
    q:              query,
    format:         'json',
    addressdetails: '1',
    limit:          String(limit),
  })

  const res = await fetch(`${NOMINATIM}?${params}`, {
    headers: { 'Accept-Language': 'en' },
  })

  if (!res.ok) throw new Error(`Nominatim error: ${res.status}`)
  const data = await res.json()

  return data.map(r => ({
    placeId: r.place_id,
    label:   r.display_name,
    // Short label: first two comma-separated parts
    shortLabel: r.display_name.split(',').slice(0, 2).join(',').trim(),
    lat:     parseFloat(r.lat),
    lon:     parseFloat(r.lon),
    type:    r.type,
    country: r.address?.country ?? '',
  }))
}

/**
 * Reverse-geocode lat/lon to a human-readable place name.
 */
export async function reverseGeocode(lat, lon) {
  const params = new URLSearchParams({
    lat:    String(lat),
    lon:    String(lon),
    format: 'json',
  })
  const res = await fetch(`https://nominatim.openstreetmap.org/reverse?${params}`, {
    headers: { 'Accept-Language': 'en' },
  })
  if (!res.ok) return `${lat.toFixed(4)}, ${lon.toFixed(4)}`
  const data = await res.json()
  return data.display_name?.split(',').slice(0, 2).join(',').trim()
    ?? `${lat.toFixed(4)}, ${lon.toFixed(4)}`
}
