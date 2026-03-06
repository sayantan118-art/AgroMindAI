import { useState, useEffect, useRef } from 'react'
import './App.css'

// Utility: Format number to 1 decimal place
const formatDecimal = (num) => parseFloat(num).toFixed(1)

// Utility: Convert polar to cartesian coordinates for 270-degree speedometer
const polarToCartesian = (centerX, centerY, radius, angleInDegrees) => {
  const angleInRadians = (angleInDegrees * Math.PI) / 180.0
  return {
    x: centerX + (radius * Math.cos(angleInRadians)),
    y: centerY + (radius * Math.sin(angleInRadians))
  }
}

// Utility: Create SVG arc path for 270-degree speedometer
const describeArc = (x, y, radius, startAngle, endAngle) => {
  const start = polarToCartesian(x, y, radius, startAngle)
  const end = polarToCartesian(x, y, radius, endAngle)
  const arcSweep = endAngle - startAngle
  const largeArcFlag = arcSweep > 180 ? "1" : "0"
  return [
    "M", start.x, start.y,
    "A", radius, radius, 0, largeArcFlag, 1, end.x, end.y
  ].join(" ")
}

// Utility: Get health color
const getHealthColor = (score) => {
  if (score < 30) return '#ef4444' // red
  if (score < 70) return '#eab308' // yellow
  return '#22c55e' // green
}

// Utility: Calculate trend arrow
const calculateTrendArrow = (current, previous) => {
  if (previous === null || previous === undefined) return '→'
  const diff = current - previous
  if (diff > 2) return '↑'
  if (diff < -2) return '↓'
  return '→'
}

// Component: Health Gauge (270-degree speedometer)
const HealthGauge = ({ healthScore, size = 200 }) => {
  const score = parseFloat(healthScore).toFixed(1)
  const centerX = size / 2
  const centerY = size / 2
  const radius = (size / 2) - 20
  
  // 270-degree speedometer: starts at 135° and sweeps 270° clockwise
  const startAngle = 135
  const totalDegrees = 270
  
  // Calculate fill angle based on score
  const fillDegrees = (parseFloat(healthScore) / 100) * totalDegrees
  const endAngle = startAngle + fillDegrees
  
  const backgroundPath = describeArc(centerX, centerY, radius, startAngle, startAngle + totalDegrees)
  const foregroundPath = describeArc(centerX, centerY, radius, startAngle, endAngle)
  const color = getHealthColor(parseFloat(healthScore))
  
  return (
    <div className="health-gauge">
      <svg width={size} height={size} viewBox={`0 0 ${size} ${size}`}>
        {/* Background arc */}
        <path
          d={backgroundPath}
          fill="none"
          stroke="#e5e7eb"
          strokeWidth="20"
          strokeLinecap="round"
        />
        {/* Foreground arc */}
        <path
          d={foregroundPath}
          fill="none"
          stroke={color}
          strokeWidth="20"
          strokeLinecap="round"
          style={{ transition: 'all 0.5s ease-out' }}
        />
        {/* Center text */}
        <text
          x={centerX}
          y={centerY}
          textAnchor="middle"
          dominantBaseline="middle"
          className="gauge-text"
          fill={color}
        >
          {score}%
        </text>
      </svg>
    </div>
  )
}

// Custom Hook: Weather Forecast
const useWeatherForecast = () => {
  const [weather, setWeather] = useState(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState(null)
  
  const fetchWeather = async () => {
    try {
      const response = await fetch('http://127.0.0.1:8000/weather/forecast')
      if (!response.ok) throw new Error('Weather API error')
      const data = await response.json()
      setWeather(data)
      setError(null)
    } catch (err) {
      setError(err.message)
      setWeather({ rain_probability_next_hour: 0, rain_expected: false, error: err.message })
    } finally {
      setLoading(false)
    }
  }
  
  useEffect(() => {
    fetchWeather()
    const interval = setInterval(fetchWeather, 15 * 60 * 1000) // 15 minutes
    return () => clearInterval(interval)
  }, [])
  
  return { weather, loading, error }
}

// Custom Hook: Pump Usage
const usePumpUsage = () => {
  const [usage, setUsage] = useState(null)
  const [loading, setLoading] = useState(true)
  
  const fetchUsage = async () => {
    try {
      const response = await fetch('http://127.0.0.1:8000/pump/usage/today')
      if (!response.ok) throw new Error('Pump usage API error')
      const data = await response.json()
      setUsage(data)
    } catch (err) {
      console.error('Pump usage fetch error:', err)
      setUsage({ total_on_seconds: 0 })
    } finally {
      setLoading(false)
    }
  }
  
  useEffect(() => {
    fetchUsage()
    const interval = setInterval(fetchUsage, 30 * 1000) // 30 seconds
    return () => clearInterval(interval)
  }, [])
  
  return { usage, loading }
}

// Custom Hook: WebSocket
const useWebSocket = (url) => {
  const [data, setData] = useState(null)
  const [connected, setConnected] = useState(false)
  const wsRef = useRef(null)
  const reconnectTimeoutRef = useRef(null)
  const reconnectDelayRef = useRef(1000)
  
  const connect = () => {
    try {
      const ws = new WebSocket(url)
      
      ws.onopen = () => {
        console.log('WebSocket connected')
        setConnected(true)
        reconnectDelayRef.current = 1000 // Reset backoff
      }
      
      ws.onmessage = (event) => {
        try {
          const message = JSON.parse(event.data)
          setData(message)
        } catch (err) {
          console.error('WebSocket message parse error:', err)
        }
      }
      
      ws.onerror = (error) => {
        console.error('WebSocket error:', error)
      }
      
      ws.onclose = () => {
        console.log('WebSocket disconnected')
        setConnected(false)
        
        // Exponential backoff reconnection
        reconnectTimeoutRef.current = setTimeout(() => {
          console.log(`Reconnecting in ${reconnectDelayRef.current}ms...`)
          reconnectDelayRef.current = Math.min(reconnectDelayRef.current * 2, 30000)
          connect()
        }, reconnectDelayRef.current)
      }
      
      wsRef.current = ws
    } catch (err) {
      console.error('WebSocket connection error:', err)
    }
  }
  
  useEffect(() => {
    connect()
    
    return () => {
      if (reconnectTimeoutRef.current) {
        clearTimeout(reconnectTimeoutRef.current)
      }
      if (wsRef.current) {
        wsRef.current.close()
      }
    }
  }, [url])
  
  return { data, connected }
}

function App() {
  const [sensorData, setSensorData] = useState(null)
  const [previousMoisture, setPreviousMoisture] = useState(null)
  const [pumpStatus, setPumpStatus] = useState('OFF')
  
  const { weather, loading: weatherLoading } = useWeatherForecast()
  const { usage, loading: usageLoading } = usePumpUsage()
  const { data: wsData, connected } = useWebSocket('ws://127.0.0.1:8000/ws/dashboard')
  
  // Fetch initial sensor data
  useEffect(() => {
    const fetchInitialData = async () => {
      try {
        const response = await fetch('http://127.0.0.1:8000/sensor/latest')
        if (response.ok) {
          const data = await response.json()
          setSensorData(data)
        }
      } catch (err) {
        console.error('Initial data fetch error:', err)
      }
    }
    
    fetchInitialData()
  }, [])
  
  // Update from WebSocket
  useEffect(() => {
    if (wsData) {
      setPreviousMoisture(sensorData?.soil_moisture || null)
      setSensorData(wsData)
    }
  }, [wsData])
  
  // Toggle pump
  const togglePump = async () => {
    try {
      const newStatus = pumpStatus === 'ON' ? 'OFF' : 'ON'
      const response = await fetch('http://127.0.0.1:8000/pump/control', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ action: newStatus })
      })
      
      if (response.ok) {
        setPumpStatus(newStatus)
      }
    } catch (err) {
      console.error('Pump control error:', err)
    }
  }
  
  if (!sensorData) {
    return (
      <div className="loading-container">
        <div className="loading-spinner"></div>
        <p>Loading dashboard...</p>
      </div>
    )
  }
  
  const moistureTrend = calculateTrendArrow(sensorData.soil_moisture, previousMoisture)
  const isLowMoisture = sensorData.soil_moisture < 30
  const pumpMinutes = usage ? Math.round(usage.total_on_seconds / 60) : 0
  
  return (
    <div className="dashboard">
      <header className="dashboard-header">
        <h1>🌱 AgroMind AI Dashboard</h1>
        <div className="connection-status">
          <span className={`status-dot ${connected ? 'connected' : 'demo-mode'}`}></span>
          <span>{connected ? 'Connected' : 'Offline - Mock Data'}</span>
        </div>
      </header>
      
      <div className="dashboard-grid">
        {/* Health Gauge */}
        <div className="card health-card">
          <h2>Crop Health</h2>
          <HealthGauge healthScore={sensorData.health_score} size={200} />
        </div>
        
        {/* AI Decision Panel */}
        <div className="card ai-panel">
          <h2>🤖 AI Decision</h2>
          <div className="decision-content">
            <p className="decision-text">{sensorData.decision}</p>
            <p className="reason-text">{sensorData.reason}</p>
            <p className="next-check">Next check: {sensorData.next_check_minutes} minutes</p>
            
            {/* Weather Forecast */}
            <div className="weather-section">
              {weatherLoading ? (
                <p className="weather-loading">Loading weather...</p>
              ) : weather?.error ? (
                <p className="weather-error">Weather data unavailable</p>
              ) : weather ? (
                <p className="weather-info">
                  🌧️ Rain probability: {parseFloat(weather.rain_probability_next_hour).toFixed(1)}% next hour
                </p>
              ) : null}
            </div>
          </div>
        </div>
        
        {/* Soil Moisture Card */}
        <div className={`card moisture-card ${isLowMoisture ? 'moisture-alert' : ''}`}>
          <h2>💧 Soil Moisture</h2>
          <div className="moisture-content">
            <p className="moisture-value">
              {parseFloat(sensorData.soil_moisture).toFixed(1)}% <span className="trend-arrow">{moistureTrend}</span>
            </p>
            {isLowMoisture && (
              <p className="alert-text">⚠️ Low moisture alert</p>
            )}
          </div>
        </div>
        
        {/* Temperature Card */}
        <div className="card">
          <h2>🌡️ Temperature</h2>
          <p className="sensor-value">{parseFloat(sensorData.temperature).toFixed(1)}°C</p>
        </div>
        
        {/* Humidity Card */}
        <div className="card">
          <h2>💨 Humidity</h2>
          <p className="sensor-value">{parseFloat(sensorData.humidity).toFixed(1)}%</p>
        </div>
        
        {/* Pump Control */}
        <div className="card pump-card">
          <h2>⚙️ Pump Control</h2>
          <button 
            className={`pump-button ${pumpStatus === 'ON' ? 'pump-on' : 'pump-off'}`}
            onClick={togglePump}
          >
            {pumpStatus === 'ON' ? '🟢 Pump ON' : '⚪ Pump OFF'}
          </button>
          
          {/* Water Usage Counter */}
          <div className="water-usage">
            {usageLoading ? (
              <p className="usage-loading">Loading...</p>
            ) : (
              <p className="usage-text">💧 Water used today: {pumpMinutes} minutes</p>
            )}
          </div>
        </div>
      </div>
      
      <footer className="dashboard-footer">
        <p>Last updated: {new Date(sensorData.ts).toLocaleString()}</p>
      </footer>
    </div>
  )
}

export default App
