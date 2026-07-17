/**
 * useWeather.js
 * React hook that manages weather state, auto-refresh (15 min),
 * loading/error states, and manual location override.
 */

import { useState, useEffect, useCallback, useRef } from 'react'
import { fetchWeather, clearWeatherCache } from '../services/weatherService'

// Default: farm coordinates from backend .env (Kolkata area)
const DEFAULT_LAT = 22.5726
const DEFAULT_LON = 88.3639
const REFRESH_INTERVAL_MS = 15 * 60 * 1000  // 15 minutes

export function useWeather(initialLat = DEFAULT_LAT, initialLon = DEFAULT_LON) {
  const [weather, setWeather]     = useState(null)
  const [loading, setLoading]     = useState(true)
  const [error, setError]         = useState(null)
  const [lat, setLat]             = useState(initialLat)
  const [lon, setLon]             = useState(initialLon)
  const timerRef                  = useRef(null)

  const load = useCallback(async (la, lo, forceRefresh = false) => {
    setLoading(true)
    setError(null)
    try {
      if (forceRefresh) clearWeatherCache(la, lo)
      const data = await fetchWeather(la, lo)
      setWeather(data)
    } catch (e) {
      setError(e.message ?? 'Failed to fetch weather')
    } finally {
      setLoading(false)
    }
  }, [])

  // Initial fetch + auto-refresh every 15 minutes
  useEffect(() => {
    load(lat, lon)
    timerRef.current = setInterval(() => load(lat, lon, true), REFRESH_INTERVAL_MS)
    return () => clearInterval(timerRef.current)
  }, [lat, lon, load])

  /** Manually set a new location */
  function setLocation(newLat, newLon) {
    setLat(newLat)
    setLon(newLon)
  }

  /** Force immediate refresh */
  function refresh() {
    load(lat, lon, true)
  }

  return { weather, loading, error, lat, lon, setLocation, refresh }
}
