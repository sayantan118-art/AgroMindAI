/**
 * weatherService.js
 * Fetches weather data from Open-Meteo (free, no API key).
 * Caches responses for 10 minutes to avoid redundant requests.
 */

const BASE_URL = 'https://api.open-meteo.com/v1/forecast'
const CACHE_TTL_MS = 10 * 60 * 1000  // 10 minutes

// Simple in-memory cache keyed by "lat,lon"
const cache = new Map()

/**
 * WMO weather interpretation codes → human label + emoji icon
 * https://open-meteo.com/en/docs#weathervariables
 */
const WMO_CODES = {
  0:  { label: 'Clear Sky',          icon: '☀️' },
  1:  { label: 'Mainly Clear',       icon: '🌤️' },
  2:  { label: 'Partly Cloudy',      icon: '⛅' },
  3:  { label: 'Overcast',           icon: '☁️' },
  45: { label: 'Foggy',              icon: '🌫️' },
  48: { label: 'Icy Fog',            icon: '🌫️' },
  51: { label: 'Light Drizzle',      icon: '🌦️' },
  53: { label: 'Drizzle',            icon: '🌦️' },
  55: { label: 'Heavy Drizzle',      icon: '🌧️' },
  61: { label: 'Light Rain',         icon: '🌧️' },
  63: { label: 'Rain',               icon: '🌧️' },
  65: { label: 'Heavy Rain',         icon: '🌧️' },
  71: { label: 'Light Snow',         icon: '🌨️' },
  73: { label: 'Snow',               icon: '❄️' },
  75: { label: 'Heavy Snow',         icon: '❄️' },
  80: { label: 'Rain Showers',       icon: '🌦️' },
  81: { label: 'Showers',            icon: '🌧️' },
  82: { label: 'Heavy Showers',      icon: '⛈️' },
  95: { label: 'Thunderstorm',       icon: '⛈️' },
  96: { label: 'Thunderstorm + Hail',icon: '⛈️' },
  99: { label: 'Thunderstorm + Hail',icon: '⛈️' },
}

function decodeWMO(code) {
  return WMO_CODES[code] ?? { label: 'Unknown', icon: '🌡️' }
}

/**
 * Fetch weather for given coordinates.
 * Returns a structured WeatherData object.
 *
 * @param {number} lat
 * @param {number} lon
 * @returns {Promise<WeatherData>}
 */
export async function fetchWeather(lat, lon) {
  const key = `${lat.toFixed(4)},${lon.toFixed(4)}`

  // Return cached data if still fresh
  const cached = cache.get(key)
  if (cached && Date.now() - cached.ts < CACHE_TTL_MS) {
    return cached.data
  }

  const params = new URLSearchParams({
    latitude:  lat,
    longitude: lon,
    current: [
      'temperature_2m',
      'relative_humidity_2m',
      'apparent_temperature',
      'weather_code',
      'wind_speed_10m',
      'uv_index',
      'precipitation_probability',
    ].join(','),
    hourly: [
      'temperature_2m',
      'precipitation_probability',
      'weather_code',
    ].join(','),
    daily: [
      'weather_code',
      'temperature_2m_max',
      'temperature_2m_min',
      'precipitation_probability_max',
      'sunrise',
      'sunset',
      'uv_index_max',
      'wind_speed_10m_max',
    ].join(','),
    timezone:      'auto',
    forecast_days: 7,
    wind_speed_unit: 'kmh',
  })

  const res = await fetch(`${BASE_URL}?${params}`)
  if (!res.ok) throw new Error(`Open-Meteo error: ${res.status}`)
  const raw = await res.json()

  const data = parseWeatherResponse(raw)
  cache.set(key, { ts: Date.now(), data })
  return data
}

/**
 * Parse the raw Open-Meteo response into a clean structure.
 */
function parseWeatherResponse(raw) {
  const c = raw.current
  const d = raw.daily
  const h = raw.hourly

  // Current conditions
  const wmo     = decodeWMO(c.weather_code)
  const current = {
    temperature:       Math.round(c.temperature_2m * 10) / 10,
    feelsLike:         Math.round(c.apparent_temperature * 10) / 10,
    humidity:          c.relative_humidity_2m,
    windSpeed:         Math.round(c.wind_speed_10m),
    uvIndex:           c.uv_index ?? 0,
    rainProbability:   c.precipitation_probability ?? 0,
    condition:         wmo.label,
    icon:              wmo.icon,
    weatherCode:       c.weather_code,
  }

  // Sunrise / sunset from daily[0]
  const sunrise = d.sunrise?.[0] ? new Date(d.sunrise[0]) : null
  const sunset  = d.sunset?.[0]  ? new Date(d.sunset[0])  : null
  current.sunrise = sunrise
    ? sunrise.toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })
    : '--:--'
  current.sunset = sunset
    ? sunset.toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })
    : '--:--'

  // Next 24-hour hourly forecast (next 24 entries)
  const nowIndex  = getNowHourIndex(h.time)
  const hourly24  = []
  for (let i = nowIndex; i < nowIndex + 24 && i < h.time.length; i++) {
    const t = new Date(h.time[i])
    hourly24.push({
      time:            t.toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' }),
      temperature:     Math.round(h.temperature_2m[i] * 10) / 10,
      rainProbability: h.precipitation_probability[i] ?? 0,
      icon:            decodeWMO(h.weather_code[i]).icon,
    })
  }

  // 7-day daily forecast
  const daily7 = d.time.map((dateStr, i) => ({
    date:            new Date(dateStr).toLocaleDateString([], { weekday: 'short', month: 'short', day: 'numeric' }),
    tempMax:         Math.round(d.temperature_2m_max[i]),
    tempMin:         Math.round(d.temperature_2m_min[i]),
    rainProbability: d.precipitation_probability_max[i] ?? 0,
    uvMax:           d.uv_index_max?.[i] ?? 0,
    windMax:         Math.round(d.wind_speed_10m_max?.[i] ?? 0),
    icon:            decodeWMO(d.weather_code[i]).icon,
    condition:       decodeWMO(d.weather_code[i]).label,
  }))

  // Agri alerts — derived from the data
  const alerts = buildAlerts(current, hourly24)

  return { current, hourly24, daily7, alerts, fetchedAt: new Date() }
}

/**
 * Find the hourly index closest to now.
 */
function getNowHourIndex(times) {
  const now = Date.now()
  let best = 0
  let bestDiff = Infinity
  times.forEach((t, i) => {
    const diff = Math.abs(new Date(t).getTime() - now)
    if (diff < bestDiff) { bestDiff = diff; best = i }
  })
  return best
}

/**
 * Build agricultural alert messages from current + hourly data.
 */
function buildAlerts(current, hourly24) {
  const alerts = []

  // Rain in next 6 hours
  const next6h = hourly24.slice(0, 6)
  const maxRain6h = Math.max(...next6h.map(h => h.rainProbability))
  if (maxRain6h >= 70) {
    alerts.push({
      type:    'info',
      icon:    '🌧️',
      message: `Rain expected (${maxRain6h}% probability in 6 h). Irrigation can be postponed.`,
    })
  }

  // High temperature
  if (current.temperature >= 35) {
    alerts.push({
      type:    'warning',
      icon:    '🌡️',
      message: `High temperature detected (${current.temperature}°C). Consider additional irrigation.`,
    })
  }

  // High wind — pesticide warning
  if (current.windSpeed >= 25) {
    alerts.push({
      type:    'caution',
      icon:    '💨',
      message: `Wind speed ${current.windSpeed} km/h. Avoid pesticide spraying.`,
    })
  }

  return alerts
}

/** Invalidate the cache for a location (useful after manual refresh). */
export function clearWeatherCache(lat, lon) {
  cache.delete(`${lat.toFixed(4)},${lon.toFixed(4)}`)
}
