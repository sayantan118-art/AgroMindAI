# Requirements Document: AgroMind Dashboard Improvements

## 1. Functional Requirements

### 1.1 Health Gauge Enhancement

**Priority**: High

**Description**: Transform the existing health gauge into a 270-degree arc speedometer that fills clockwise based on the health score.

**Acceptance Criteria**:
- 1.1.1 The gauge displays as a 270-degree arc starting at bottom-left (-135°) and ending at bottom-right (+135°)
- 1.1.2 The arc fills clockwise proportionally to the health score (0-100%)
- 1.1.3 The gauge uses color coding: red (0-29), yellow (30-69), green (70-100)
- 1.1.4 The numeric health score is displayed in the center of the gauge
- 1.1.5 The arc animates smoothly when the health score changes
- 1.1.6 The gauge is rendered using SVG for scalability

---

### 1.2 Weather Forecast Integration

**Priority**: High

**Description**: Add weather forecast information to the AI Decision Panel by integrating with the backend weather API.

**Acceptance Criteria**:
- 1.2.1 The system fetches weather data from GET http://localhost:8000/weather/forecast
- 1.2.2 Rain probability is displayed in the format: "🌧️ Rain probability: X% next hour"
- 1.2.3 Weather data refreshes automatically every 15 minutes
- 1.2.4 The display shows a loading state during initial fetch
- 1.2.5 If the API fails, a fallback message "Weather data unavailable" is shown
- 1.2.6 The weather section is visually integrated into the existing AI Decision Panel

---

### 1.3 Soil Moisture Alert System

**Priority**: High

**Description**: Enhance the soil moisture card with visual alerts when moisture drops below critical threshold.

**Acceptance Criteria**:
- 1.3.1 When soil moisture falls below 30%, a red pulsing glow animation is applied to the card
- 1.3.2 The pulsing animation cycles every 1.5 seconds
- 1.3.3 The alert automatically clears when moisture rises to 30% or above
- 1.3.4 The card maintains its existing layout and styling
- 1.3.5 The alert is visible but not distracting to the user
- 1.3.6 The animation uses CSS keyframes for performance

---

### 1.4 Soil Moisture Trend Indicator

**Priority**: Medium

**Description**: Display trend arrows showing whether soil moisture is increasing, decreasing, or stable compared to the previous reading.

**Acceptance Criteria**:
- 1.4.1 An upward arrow (↑) is shown when moisture increases by more than 2%
- 1.4.2 A downward arrow (↓) is shown when moisture decreases by more than 2%
- 1.4.3 A horizontal arrow (→) is shown when moisture change is within ±2%
- 1.4.4 The trend arrow is displayed next to the moisture percentage
- 1.4.5 On the first reading (no previous data), a horizontal arrow is shown
- 1.4.6 The trend updates in real-time via WebSocket messages

---

### 1.5 Water Usage Counter

**Priority**: High

**Description**: Display total pump ON time for the current day below the pump control button.

**Acceptance Criteria**:
- 1.5.1 The counter fetches data from GET http://localhost:8000/pump/usage/today
- 1.5.2 Total pump ON time is displayed in minutes (rounded)
- 1.5.3 The display format is: "💧 Water used today: X minutes"
- 1.5.4 The counter is positioned directly below the pump button
- 1.5.5 Data refreshes automatically every 30 seconds
- 1.5.6 A loading state is shown during initial fetch

---

## 2. Non-Functional Requirements

### 2.1 Performance

**Priority**: High

**Requirements**:
- 2.1.1 Initial dashboard load completes within 2 seconds
- 2.1.2 WebSocket updates render within 100ms of message receipt
- 2.1.3 Health gauge animation maintains 60 FPS
- 2.1.4 API requests complete within 500ms (95th percentile)
- 2.1.5 Memory usage remains below 50MB after 24 hours of operation

---

### 2.2 Reliability

**Priority**: High

**Requirements**:
- 2.2.1 Dashboard continues operating if weather API fails
- 2.2.2 Dashboard continues operating if pump usage API fails
- 2.2.3 WebSocket disconnections trigger automatic reconnection
- 2.2.4 Invalid sensor data is ignored without crashing the application
- 2.2.5 All timers are properly cleaned up on component unmount

---

### 2.3 Usability

**Priority**: Medium

**Requirements**:
- 2.3.1 All new features integrate seamlessly with existing UI design
- 2.3.2 Color choices meet WCAG AA contrast requirements
- 2.3.3 Animations are smooth and non-distracting
- 2.3.4 Loading states provide clear feedback to users
- 2.3.5 Error messages are user-friendly and actionable

---

### 2.4 Maintainability

**Priority**: Medium

**Requirements**:
- 2.4.1 Components are modular and reusable
- 2.4.2 Code follows React best practices and hooks patterns
- 2.4.3 Custom hooks encapsulate data fetching logic
- 2.4.4 Utility functions are pure and testable
- 2.4.5 Code is documented with JSDoc comments

---

### 2.5 Compatibility

**Priority**: Medium

**Requirements**:
- 2.5.1 Dashboard works in Chrome, Firefox, Safari, and Edge (latest versions)
- 2.5.2 SVG rendering is consistent across browsers
- 2.5.3 WebSocket connections work with standard WebSocket implementations
- 2.5.4 CSS animations are hardware-accelerated where possible
- 2.5.5 Responsive design adapts to screen sizes 1024px and above

---

## 3. Technical Requirements

### 3.1 Frontend Architecture

**Priority**: High

**Requirements**:
- 3.1.1 Use React functional components with hooks
- 3.1.2 Implement custom hooks for API data fetching
- 3.1.3 Use native fetch API for HTTP requests
- 3.1.4 Use native WebSocket API for real-time updates
- 3.1.5 Apply Tailwind CSS for styling
- 3.1.6 Use SVG for health gauge rendering

---

### 3.2 State Management

**Priority**: High

**Requirements**:
- 3.2.1 Use React useState for component-level state
- 3.2.2 Use useEffect for side effects and data fetching
- 3.2.3 Store previous moisture reading for trend calculation
- 3.2.4 Maintain WebSocket connection state
- 3.2.5 Track loading and error states for all async operations

---

### 3.3 API Integration

**Priority**: High

**Requirements**:
- 3.3.1 Integrate with GET /sensor/latest for initial data
- 3.3.2 Integrate with GET /weather/forecast for weather data
- 3.3.3 Integrate with GET /pump/usage/today for water usage
- 3.3.4 Integrate with WS /ws/dashboard for real-time updates
- 3.3.5 Handle API errors gracefully with fallback values
- 3.3.6 Implement automatic retry logic for failed requests

---

### 3.4 Data Validation

**Priority**: Medium

**Requirements**:
- 3.4.1 Validate sensor data ranges: moisture (0-100), health (0-100)
- 3.4.2 Validate weather data structure before display
- 3.4.3 Validate pump usage data is non-negative
- 3.4.4 Ignore invalid WebSocket messages
- 3.4.5 Log validation errors for debugging

---

## 4. Constraints

### 4.1 UI Preservation

**Priority**: Critical

**Requirements**:
- 4.1.1 Do not modify any existing UI components not specified in requirements
- 4.1.2 Maintain existing dashboard layout and grid structure
- 4.1.3 Preserve existing color scheme and typography
- 4.1.4 Keep existing pump button functionality unchanged
- 4.1.5 Do not alter existing component hierarchy

---

### 4.2 Backend Integration

**Priority**: Critical

**Requirements**:
- 4.2.1 Use existing backend API at localhost:8000
- 4.2.2 Do not modify backend endpoints or data structures
- 4.2.3 Work with existing WebSocket message format
- 4.2.4 Respect existing API response structures
- 4.2.5 No new backend dependencies required

---

### 4.3 Technology Stack

**Priority**: High

**Requirements**:
- 4.3.1 Use React 18.x as specified in package.json
- 4.3.2 Use Vite as the build tool
- 4.3.3 Use Tailwind CSS for styling
- 4.3.4 No additional heavy dependencies (keep bundle size minimal)
- 4.3.5 Use native browser APIs where possible

---

## 5. Data Requirements

### 5.1 Sensor Data Structure

**Priority**: High

**Requirements**:
- 5.1.1 Consume sensor data with fields: soil_moisture, health_score, temperature, humidity
- 5.1.2 Handle timestamp field (ts) for data freshness
- 5.1.3 Process decision and reason fields for AI panel
- 5.1.4 Store previous moisture value for trend calculation
- 5.1.5 Validate all numeric fields are within expected ranges

---

### 5.2 Weather Data Structure

**Priority**: High

**Requirements**:
- 5.2.1 Consume weather data with field: rain_probability_next_hour (0-100)
- 5.2.2 Handle optional error field for API failures
- 5.2.3 Cache weather data for up to 15 minutes
- 5.2.4 Provide default values when data is unavailable

---

### 5.3 Pump Usage Data Structure

**Priority**: High

**Requirements**:
- 5.3.1 Consume pump usage data with field: total_on_seconds
- 5.3.2 Handle date field to verify current day data
- 5.3.3 Convert seconds to minutes for display
- 5.3.4 Round to nearest minute (>= 30 seconds rounds up)

---

## 6. Testing Requirements

### 6.1 Unit Testing

**Priority**: Medium

**Requirements**:
- 6.1.1 Test health gauge arc calculation for various scores
- 6.1.2 Test trend arrow logic for all scenarios
- 6.1.3 Test color mapping function for all ranges
- 6.1.4 Test seconds-to-minutes conversion
- 6.1.5 Achieve minimum 80% code coverage

---

### 6.2 Integration Testing

**Priority**: Medium

**Requirements**:
- 6.2.1 Test complete dashboard load with all components
- 6.2.2 Test WebSocket real-time update flow
- 6.2.3 Test weather API integration
- 6.2.4 Test pump usage API integration
- 6.2.5 Test error handling for all API failures

---

### 6.3 Visual Testing

**Priority**: Low

**Requirements**:
- 6.3.1 Verify health gauge renders correctly at different scores
- 6.3.2 Verify pulsing glow animation is visible and smooth
- 6.3.3 Verify trend arrows display correctly
- 6.3.4 Verify layout remains intact with new components
- 6.3.5 Test across different screen sizes

---

## 7. Documentation Requirements

### 7.1 Code Documentation

**Priority**: Low

**Requirements**:
- 7.1.1 Add JSDoc comments to all custom hooks
- 7.1.2 Add JSDoc comments to utility functions
- 7.1.3 Document component props with PropTypes or TypeScript
- 7.1.4 Include inline comments for complex logic
- 7.1.5 Document API integration points

---

### 7.2 User Documentation

**Priority**: Low

**Requirements**:
- 7.2.1 No user documentation required (UI is self-explanatory)
- 7.2.2 Error messages provide sufficient guidance
- 7.2.3 Visual indicators are intuitive

---

## 8. Security Requirements

### 8.1 Input Validation

**Priority**: Medium

**Requirements**:
- 8.1.1 Validate all API responses before processing
- 8.1.2 Sanitize any user-generated content before display
- 8.1.3 Validate WebSocket message structure
- 8.1.4 Reject out-of-range numeric values
- 8.1.5 Log security-relevant events

---

### 8.2 Network Security

**Priority**: Low

**Requirements**:
- 8.2.1 Use localhost URLs for development (as specified)
- 8.2.2 Prepare for HTTPS/WSS in production (future)
- 8.2.3 Implement proper CORS handling
- 8.2.4 No sensitive data in browser storage

---

## 9. Deployment Requirements

### 9.1 Build Process

**Priority**: Medium

**Requirements**:
- 9.1.1 Build process completes without errors
- 9.1.2 Production build is optimized and minified
- 9.1.3 Bundle size remains reasonable (< 500KB gzipped)
- 9.1.4 Source maps are generated for debugging
- 9.1.5 Build artifacts are ready for static hosting

---

### 9.2 Environment Configuration

**Priority**: Medium

**Requirements**:
- 9.2.1 Backend API URL is configurable via environment variables
- 9.2.2 WebSocket URL is configurable via environment variables
- 9.2.3 Refresh intervals are configurable
- 9.2.4 Development and production configs are separate

---

## 10. Success Metrics

### 10.1 Functional Metrics

**Priority**: High

**Metrics**:
- 10.1.1 All four improvements are implemented and functional
- 10.1.2 Health gauge displays correctly for all score ranges
- 10.1.3 Weather data updates every 15 minutes
- 10.1.4 Pump usage updates every 30 seconds
- 10.1.5 Moisture alerts trigger at correct threshold

---

### 10.2 Performance Metrics

**Priority**: High

**Metrics**:
- 10.2.1 Dashboard loads in under 2 seconds
- 10.2.2 WebSocket updates render in under 100ms
- 10.2.3 No memory leaks after 24 hours
- 10.2.4 Animations run at 60 FPS
- 10.2.5 API response times under 500ms

---

### 10.3 Quality Metrics

**Priority**: Medium

**Metrics**:
- 10.3.1 Zero console errors during normal operation
- 10.3.2 Graceful degradation on API failures
- 10.3.3 Code passes linting without errors
- 10.3.4 Unit test coverage above 80%
- 10.3.5 No accessibility violations (WCAG AA)

---

