# Tasks: AgroMind Dashboard Improvements

## 1. Project Setup and Preparation

- [ ] 1.1 Review existing dashboard code structure and component hierarchy
- [ ] 1.2 Identify current state management patterns in App.jsx
- [ ] 1.3 Verify backend API endpoints are accessible and returning expected data
- [ ] 1.4 Test WebSocket connection to ws://localhost:8000/ws/dashboard

---

## 2. Health Gauge Component (270-degree Arc Speedometer)

- [ ] 2.1 Create HealthGauge component file
  - [ ] 2.1.1 Set up component structure with props interface
  - [ ] 2.1.2 Define default props (size: 200px)
  - [ ] 2.1.3 Add PropTypes or TypeScript types

- [ ] 2.2 Implement SVG arc rendering logic
  - [ ] 2.2.1 Create polarToCartesian utility function
  - [ ] 2.2.2 Create describeArc utility function for SVG path generation
  - [ ] 2.2.3 Calculate arc parameters (start: -135°, end: 135°, total: 270°)
  - [ ] 2.2.4 Generate background arc (light gray)
  - [ ] 2.2.5 Generate foreground arc based on health score

- [ ] 2.3 Implement color mapping logic
  - [ ] 2.3.1 Create getHealthColor utility function
  - [ ] 2.3.2 Map 0-29 to red (#ef4444)
  - [ ] 2.3.3 Map 30-69 to yellow (#eab308)
  - [ ] 2.3.4 Map 70-100 to green (#22c55e)

- [ ] 2.4 Add center text display
  - [ ] 2.4.1 Position text in center of arc
  - [ ] 2.4.2 Display health score with "%" suffix
  - [ ] 2.4.3 Style text (large, bold font)

- [ ] 2.5 Add animation for value changes
  - [ ] 2.5.1 Implement CSS transition for arc fill
  - [ ] 2.5.2 Set transition duration (0.5s ease-out)
  - [ ] 2.5.3 Test animation smoothness

- [ ] 2.6 Integrate HealthGauge into App.jsx
  - [ ] 2.6.1 Import HealthGauge component
  - [ ] 2.6.2 Replace existing health display with HealthGauge
  - [ ] 2.6.3 Pass health_score from sensor data
  - [ ] 2.6.4 Verify rendering and positioning

---

## 3. Weather Forecast Integration

- [ ] 3.1 Create useWeatherForecast custom hook
  - [ ] 3.1.1 Set up hook structure with state (weather, loading, error)
  - [ ] 3.1.2 Implement fetch logic for /weather/forecast endpoint
  - [ ] 3.1.3 Add error handling with try-catch
  - [ ] 3.1.4 Return safe default values on error

- [ ] 3.2 Implement automatic refresh logic
  - [ ] 3.2.1 Set up useEffect with interval timer (15 minutes)
  - [ ] 3.2.2 Fetch weather data on component mount
  - [ ] 3.2.3 Clear interval on component unmount
  - [ ] 3.2.4 Prevent multiple simultaneous fetches

- [ ] 3.3 Create WeatherForecast display component
  - [ ] 3.3.1 Create component structure
  - [ ] 3.3.2 Add loading state display
  - [ ] 3.3.3 Add error state display ("Weather data unavailable")
  - [ ] 3.3.4 Format display: "🌧️ Rain probability: X% next hour"

- [ ] 3.4 Integrate weather into AI Decision Panel
  - [ ] 3.4.1 Locate existing AI Decision Panel in App.jsx
  - [ ] 3.4.2 Add WeatherForecast component to panel
  - [ ] 3.4.3 Style to match existing panel design
  - [ ] 3.4.4 Test data refresh cycle

---

## 4. Soil Moisture Alert System

- [ ] 4.1 Create CSS animation for pulsing glow
  - [ ] 4.1.1 Define @keyframes pulse-glow animation
  - [ ] 4.1.2 Set animation cycle to 1.5 seconds
  - [ ] 4.1.3 Animate box-shadow from 5px to 20px blur
  - [ ] 4.1.4 Use red color (#ef4444) for glow

- [ ] 4.2 Create alert CSS class
  - [ ] 4.2.1 Add .moisture-alert class with red border
  - [ ] 4.2.2 Apply pulse-glow animation
  - [ ] 4.2.3 Set animation to infinite loop
  - [ ] 4.2.4 Ensure animation is hardware-accelerated

- [ ] 4.3 Implement alert logic in component
  - [ ] 4.3.1 Check if soil_moisture < 30
  - [ ] 4.3.2 Conditionally apply .moisture-alert class
  - [ ] 4.3.3 Update class when moisture value changes
  - [ ] 4.3.4 Test alert activation and deactivation

- [ ] 4.4 Integrate alert into existing soil moisture card
  - [ ] 4.4.1 Locate soil moisture card in App.jsx
  - [ ] 4.4.2 Add conditional className logic
  - [ ] 4.4.3 Verify existing styling is preserved
  - [ ] 4.4.4 Test visual appearance

---

## 5. Soil Moisture Trend Indicator

- [ ] 5.1 Create trend calculation utility
  - [ ] 5.1.1 Create calculateTrendArrow function
  - [ ] 5.1.2 Implement upward trend logic (difference > 2%)
  - [ ] 5.1.3 Implement downward trend logic (difference < -2%)
  - [ ] 5.1.4 Implement stable trend logic (within ±2%)
  - [ ] 5.1.5 Handle null previous value case

- [ ] 5.2 Add state for previous moisture reading
  - [ ] 5.2.1 Add previousMoisture state variable in App.jsx
  - [ ] 5.2.2 Update previousMoisture when new data arrives
  - [ ] 5.2.3 Initialize to null on first load

- [ ] 5.3 Implement trend arrow display
  - [ ] 5.3.1 Calculate trend using utility function
  - [ ] 5.3.2 Display arrow (↑, ↓, or →) next to moisture percentage
  - [ ] 5.3.3 Style arrow for visibility
  - [ ] 5.3.4 Update arrow on WebSocket messages

- [ ] 5.4 Test trend calculation
  - [ ] 5.4.1 Test with increasing moisture values
  - [ ] 5.4.2 Test with decreasing moisture values
  - [ ] 5.4.3 Test with stable moisture values
  - [ ] 5.4.4 Test first reading (no previous data)

---

## 6. Water Usage Counter

- [ ] 6.1 Create usePumpUsage custom hook
  - [ ] 6.1.1 Set up hook structure with state (usage, loading, error)
  - [ ] 6.1.2 Implement fetch logic for /pump/usage/today endpoint
  - [ ] 6.1.3 Add error handling with try-catch
  - [ ] 6.1.4 Return safe default values on error

- [ ] 6.2 Implement automatic refresh logic
  - [ ] 6.2.1 Set up useEffect with interval timer (30 seconds)
  - [ ] 6.2.2 Fetch pump usage on component mount
  - [ ] 6.2.3 Clear interval on component unmount
  - [ ] 6.2.4 Prevent multiple simultaneous fetches

- [ ] 6.3 Create seconds-to-minutes conversion utility
  - [ ] 6.3.1 Create convertSecondsToMinutes function
  - [ ] 6.3.2 Implement rounding logic (>= 30 seconds rounds up)
  - [ ] 6.3.3 Handle zero and large values
  - [ ] 6.3.4 Return formatted string

- [ ] 6.4 Create WaterUsageCounter component
  - [ ] 6.4.1 Create component structure
  - [ ] 6.4.2 Use usePumpUsage hook
  - [ ] 6.4.3 Convert seconds to minutes
  - [ ] 6.4.4 Format display: "💧 Water used today: X minutes"
  - [ ] 6.4.5 Add loading state display

- [ ] 6.5 Integrate counter below pump button
  - [ ] 6.5.1 Locate pump button in App.jsx
  - [ ] 6.5.2 Add WaterUsageCounter component below button
  - [ ] 6.5.3 Style for proper positioning and spacing
  - [ ] 6.5.4 Test data refresh cycle

---

## 7. WebSocket Integration Enhancement

- [ ] 7.1 Review existing WebSocket connection logic
  - [ ] 7.1.1 Identify current WebSocket implementation
  - [ ] 7.1.2 Verify message handling for sensor data
  - [ ] 7.1.3 Check connection lifecycle management

- [ ] 7.2 Enhance WebSocket message handler
  - [ ] 7.2.1 Add validation for incoming messages
  - [ ] 7.2.2 Update previousMoisture before updating current
  - [ ] 7.2.3 Trigger trend calculation on new data
  - [ ] 7.2.4 Trigger alert check on new data

- [ ] 7.3 Implement reconnection logic (if not present)
  - [ ] 7.3.1 Detect connection loss
  - [ ] 7.3.2 Implement exponential backoff (1s, 2s, 4s, 8s, max 30s)
  - [ ] 7.3.3 Reset backoff on successful connection
  - [ ] 7.3.4 Log connection status changes

---

## 8. Error Handling and Resilience

- [ ] 8.1 Implement weather API error handling
  - [ ] 8.1.1 Display fallback message on error
  - [ ] 8.1.2 Use cached data if available (< 1 hour old)
  - [ ] 8.1.3 Log errors to console
  - [ ] 8.1.4 Retry on next scheduled refresh

- [ ] 8.2 Implement pump usage API error handling
  - [ ] 8.2.1 Display "0 minutes" as safe default
  - [ ] 8.2.2 Show loading indicator instead of error
  - [ ] 8.2.3 Log errors to console
  - [ ] 8.2.4 Retry on next scheduled refresh

- [ ] 8.3 Implement WebSocket error handling
  - [ ] 8.3.1 Continue showing last known data on disconnect
  - [ ] 8.3.2 Attempt automatic reconnection
  - [ ] 8.3.3 Log connection status
  - [ ] 8.3.4 Fall back to polling if WebSocket unavailable

- [ ] 8.4 Implement data validation
  - [ ] 8.4.1 Validate sensor data ranges
  - [ ] 8.4.2 Validate weather data structure
  - [ ] 8.4.3 Validate pump usage data
  - [ ] 8.4.4 Ignore invalid messages

---

## 9. Testing

- [ ] 9.1 Unit tests for utility functions
  - [ ] 9.1.1 Test polarToCartesian function
  - [ ] 9.1.2 Test describeArc function
  - [ ] 9.1.3 Test getHealthColor function
  - [ ] 9.1.4 Test calculateTrendArrow function
  - [ ] 9.1.5 Test convertSecondsToMinutes function

- [ ] 9.2 Component tests
  - [ ] 9.2.1 Test HealthGauge rendering at different scores
  - [ ] 9.2.2 Test WeatherForecast component states
  - [ ] 9.2.3 Test WaterUsageCounter component states
  - [ ] 9.2.4 Test soil moisture alert activation

- [ ] 9.3 Integration tests
  - [ ] 9.3.1 Test complete dashboard load
  - [ ] 9.3.2 Test WebSocket update flow
  - [ ] 9.3.3 Test weather API integration
  - [ ] 9.3.4 Test pump usage API integration

- [ ] 9.4 Manual testing
  - [ ] 9.4.1 Test in Chrome browser
  - [ ] 9.4.2 Test in Firefox browser
  - [ ] 9.4.3 Test with backend running
  - [ ] 9.4.4 Test with backend stopped (error handling)
  - [ ] 9.4.5 Test WebSocket reconnection

---

## 10. Performance Optimization

- [ ] 10.1 Optimize component rendering
  - [ ] 10.1.1 Add React.memo to HealthGauge component
  - [ ] 10.1.2 Debounce WebSocket updates if needed
  - [ ] 10.1.3 Use CSS transforms for animations
  - [ ] 10.1.4 Verify 60 FPS animation performance

- [ ] 10.2 Optimize network requests
  - [ ] 10.2.1 Implement request deduplication
  - [ ] 10.2.2 Add HTTP caching headers consideration
  - [ ] 10.2.3 Verify no memory leaks from timers

- [ ] 10.3 Performance testing
  - [ ] 10.3.1 Measure initial load time (target: < 2s)
  - [ ] 10.3.2 Measure WebSocket update latency (target: < 100ms)
  - [ ] 10.3.3 Monitor memory usage over time
  - [ ] 10.3.4 Profile animation frame rate

---

## 11. Code Quality and Documentation

- [ ] 11.1 Add code documentation
  - [ ] 11.1.1 Add JSDoc comments to custom hooks
  - [ ] 11.1.2 Add JSDoc comments to utility functions
  - [ ] 11.1.3 Add inline comments for complex logic
  - [ ] 11.1.4 Document component props

- [ ] 11.2 Code review and cleanup
  - [ ] 11.2.1 Run ESLint and fix warnings
  - [ ] 11.2.2 Remove console.log statements (keep error logs)
  - [ ] 11.2.3 Ensure consistent code formatting
  - [ ] 11.2.4 Remove unused imports and variables

- [ ] 11.3 Verify constraints
  - [ ] 11.3.1 Confirm no unintended UI changes
  - [ ] 11.3.2 Verify existing components still work
  - [ ] 11.3.3 Confirm no new backend dependencies
  - [ ] 11.3.4 Verify bundle size is reasonable

---

## 12. Final Integration and Validation

- [ ] 12.1 End-to-end testing
  - [ ] 12.1.1 Start backend server
  - [ ] 12.1.2 Load dashboard and verify all features
  - [ ] 12.1.3 Test real-time updates via WebSocket
  - [ ] 12.1.4 Test all API integrations
  - [ ] 12.1.5 Test error scenarios

- [ ] 12.2 Visual validation
  - [ ] 12.2.1 Verify health gauge displays correctly
  - [ ] 12.2.2 Verify weather forecast displays correctly
  - [ ] 12.2.3 Verify soil moisture alert animation
  - [ ] 12.2.4 Verify trend arrows display correctly
  - [ ] 12.2.5 Verify water usage counter displays correctly

- [ ] 12.3 Acceptance criteria validation
  - [ ] 12.3.1 Verify all requirements from requirements.md are met
  - [ ] 12.3.2 Test all acceptance criteria
  - [ ] 12.3.3 Verify performance targets are met
  - [ ] 12.3.4 Confirm no regressions in existing functionality

- [ ] 12.4 Build and deployment preparation
  - [ ] 12.4.1 Run production build
  - [ ] 12.4.2 Verify build completes without errors
  - [ ] 12.4.3 Test production build locally
  - [ ] 12.4.4 Verify bundle size is acceptable

---

