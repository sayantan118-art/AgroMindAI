/*
 * AgroMind AI - ESP32 Firmware
 * Complete sensor monitoring and irrigation control system
 * 
 * Hardware Configuration:
 * - Soil Moisture Sensor → GPIO 34 (analog)
 * - DHT22 → GPIO 4 (digital)
 * - Rain Sensor → GPIO 18 (digital)
 * - LDR Light Sensor → GPIO 35 (analog)
 * - Relay → GPIO 26 (digital)
 * - LED → GPIO 2 (built-in LED)
 * 
 * MQTT Topics:
 * - Publish: agromind/sensors (every 10 seconds)
 * - Subscribe: agromind/pump (for pump control)
 * 
 * Soil Moisture Calibration:
 * - Raw 4095 = 0% (completely dry)
 * - Raw 1500 = 100% (completely wet)
 * - Clamped to 0-100% range
 */

// ==================== LIBRARIES ====================
#include <WiFi.h>
#include <PubSubClient.h>
#include <ArduinoJson.h>
#include <DHT.h>

// ==================== PIN DEFINITIONS ====================
#define SOIL_MOISTURE_PIN 34    // Analog input for soil moisture
#define DHT_PIN 4               // Digital input for DHT22
#define RAIN_SENSOR_PIN 18      // Digital input for rain sensor
#define LDR_PIN 35              // Analog input for light sensor
#define RELAY_PIN 26            // Digital output for pump relay
#define LED_PIN 2               // Built-in LED for status

// ==================== NETWORK CONFIGURATION ====================
#define WIFI_SSID "Sayantan's Mobile"
#define WIFI_PASS "sayantan"
#define MQTT_BROKER "10.64.168.176"
#define MQTT_PORT 1883

// ==================== SENSOR CONFIGURATION ====================
#define DHT_TYPE DHT22          // DHT22 sensor type
#define SOIL_DRY_VALUE 4095     // Raw ADC value when completely dry
#define SOIL_WET_VALUE 1500     // Raw ADC value when completely wet
#define PUMP_TIMEOUT_MS 180000  // 180 seconds = 3 minutes pump timeout
#define PUBLISH_INTERVAL_MS 10000 // 10 seconds between sensor publishes

// ==================== GLOBAL OBJECTS ====================
WiFiClient espClient;
PubSubClient mqttClient(espClient);
DHT dht(DHT_PIN, DHT_TYPE);

// ==================== GLOBAL VARIABLES ====================
unsigned long lastPublishTime = 0;
unsigned long lastReconnectAttempt = 0;
unsigned long pumpStartTime = 0;
bool pumpActive = false;
bool ledState = false;

// ==================== FUNCTION PROTOTYPES ====================
void setupWiFi();
void setupMQTT();
void reconnectMQTT();
void publishSensorData();
void mqttCallback(char* topic, byte* payload, unsigned int length);
float readSoilMoisture();
float readLightLevel();
bool readRainStatus();
void controlPump(bool state);
void blinkLED();

// ==================== SETUP FUNCTION ====================
void setup() {
  // Initialize serial communication
  Serial.begin(115200);
  Serial.println("\n\n========================================");
  Serial.println("AgroMind AI - ESP32 Firmware Starting");
  Serial.println("========================================");
  
  // Initialize pins
  pinMode(SOIL_MOISTURE_PIN, INPUT);
  pinMode(RAIN_SENSOR_PIN, INPUT_PULLUP); // Rain sensor typically active LOW
  pinMode(LDR_PIN, INPUT);
  pinMode(RELAY_PIN, OUTPUT);
  pinMode(LED_PIN, OUTPUT);
  
  // Initialize relay to OFF (LOW = relay OFF, HIGH = relay ON)
  digitalWrite(RELAY_PIN, LOW);
  digitalWrite(LED_PIN, LOW);
  
  // Initialize DHT sensor
  dht.begin();
  delay(1000); // Give DHT sensor time to initialize
  
  // Connect to WiFi
  setupWiFi();
  
  // Setup MQTT
  setupMQTT();
  
  Serial.println("Setup complete. Starting main loop...");
}

// ==================== MAIN LOOP ====================
void loop() {
  unsigned long currentMillis = millis();
  
  // Maintain MQTT connection
  if (!mqttClient.connected()) {
    reconnectMQTT();
  }
  mqttClient.loop();
  
  // Publish sensor data every 10 seconds
  if (currentMillis - lastPublishTime >= PUBLISH_INTERVAL_MS) {
    publishSensorData();
    lastPublishTime = currentMillis;
    blinkLED(); // Blink LED on each publish
  }
  
  // Check pump timeout
  if (pumpActive && (currentMillis - pumpStartTime >= PUMP_TIMEOUT_MS)) {
    Serial.println("Pump timeout reached. Turning OFF.");
    controlPump(false);
  }
  
  // Small delay to prevent watchdog timer issues
  delay(10);
}

// ==================== WIFI SETUP ====================
void setupWiFi() {
  Serial.print("Connecting to WiFi: ");
  Serial.println(WIFI_SSID);
  
  WiFi.begin(WIFI_SSID, WIFI_PASS);
  
  int attempts = 0;
  while (WiFi.status() != WL_CONNECTED && attempts < 20) {
    delay(500);
    Serial.print(".");
    attempts++;
  }
  
  if (WiFi.status() == WL_CONNECTED) {
    Serial.println("\nWiFi connected!");
    Serial.print("IP Address: ");
    Serial.println(WiFi.localIP());
    Serial.print("MAC Address: ");
    Serial.println(WiFi.macAddress());
  } else {
    Serial.println("\nWiFi connection failed!");
  }
}

// ==================== MQTT SETUP ====================
void setupMQTT() {
  mqttClient.setServer(MQTT_BROKER, MQTT_PORT);
  mqttClient.setCallback(mqttCallback);
  mqttClient.setBufferSize(1024); // Increase buffer for JSON messages
}

// ==================== MQTT RECONNECT ====================
void reconnectMQTT() {
  unsigned long currentMillis = millis();
  
  // Only attempt reconnect every 5 seconds
  if (currentMillis - lastReconnectAttempt < 5000) {
    return;
  }
  
  lastReconnectAttempt = currentMillis;
  
  Serial.print("Attempting MQTT connection...");
  
  // Generate unique client ID
  String clientId = "AgroMind-ESP32-";
  clientId += String(random(0xffff), HEX);
  
  // Attempt to connect
  if (mqttClient.connect(clientId.c_str())) {
    Serial.println("connected!");
    
    // Subscribe to pump control topic
    mqttClient.subscribe("agromind/pump");
    Serial.println("Subscribed to: agromind/pump");
    
  } else {
    Serial.print("failed, rc=");
    Serial.print(mqttClient.state());
    Serial.println(" trying again in 5 seconds");
  }
}

// ==================== MQTT CALLBACK ====================
void mqttCallback(char* topic, byte* payload, unsigned int length) {
  Serial.print("Message arrived [");
  Serial.print(topic);
  Serial.print("]: ");
  
  // Convert payload to string
  String message;
  for (unsigned int i = 0; i < length; i++) {
    message += (char)payload[i];
  }
  Serial.println(message);
  
  // Check if message is for pump control
  if (String(topic) == "agromind/pump") {
    if (message == "ON") {
      Serial.println("Pump command: ON");
      controlPump(true);
    } else if (message == "OFF") {
      Serial.println("Pump command: OFF");
      controlPump(false);
    } else {
      Serial.print("Unknown pump command: ");
      Serial.println(message);
    }
  }
}

// ==================== SENSOR DATA PUBLISH ====================
void publishSensorData() {
  // Read all sensors
  float soilMoisture = readSoilMoisture();
  float temperature = dht.readTemperature();
  float humidity = dht.readHumidity();
  float lightLevel = readLightLevel();
  bool rainDetected = readRainStatus();
  
  // Check if DHT readings failed
  if (isnan(temperature) || isnan(humidity)) {
    Serial.println("Failed to read from DHT sensor!");
    temperature = 25.0; // Default values
    humidity = 60.0;
  }
  
  // Create JSON document
  StaticJsonDocument<256> jsonDoc;
  
  // Add sensor data
  jsonDoc["soil_moisture"] = soilMoisture;
  jsonDoc["temperature"] = temperature;
  jsonDoc["humidity"] = humidity;
  jsonDoc["light"] = lightLevel;
  jsonDoc["rain_detected"] = rainDetected;
  jsonDoc["pump_active"] = pumpActive;
  jsonDoc["timestamp"] = millis();
  
  // Serialize JSON to string
  char jsonBuffer[256];
  serializeJson(jsonDoc, jsonBuffer);
  
  // Publish to MQTT
  if (mqttClient.publish("agromind/sensors", jsonBuffer)) {
    Serial.print("Published: ");
    Serial.println(jsonBuffer);
  } else {
    Serial.println("Failed to publish sensor data!");
  }
}

// ==================== SOIL MOISTURE READING ====================
float readSoilMoisture() {
  // Read raw ADC value (0-4095 for ESP32)
  int rawValue = analogRead(SOIL_MOISTURE_PIN);
  
  // Convert to percentage (inverse: higher raw = drier)
  // Map raw value to percentage (inverted because higher raw = drier)
  float percentage = map(rawValue, SOIL_DRY_VALUE, SOIL_WET_VALUE, 0, 100);
  
  // Clamp to 0-100% range
  percentage = constrain(percentage, 0, 100);
  
  // Debug output
  Serial.print("Soil Moisture - Raw: ");
  Serial.print(rawValue);
  Serial.print(", Percentage: ");
  Serial.print(percentage);
  Serial.println("%");
  
  return percentage;
}

// ==================== LIGHT LEVEL READING ====================
float readLightLevel() {
  // Read raw ADC value from LDR
  int rawValue = analogRead(LDR_PIN);
  
  // LDR typically: higher value = darker, lower value = brighter
  // We'll return raw value for now, can be converted to lux if calibrated
  Serial.print("Light Level - Raw: ");
  Serial.println(rawValue);
  
  return (float)rawValue;
}

// ==================== RAIN SENSOR READING ====================
bool readRainStatus() {
  // Rain sensor typically: LOW when rain detected, HIGH when dry
  // Using INPUT_PULLUP, so we invert the reading
  bool rainDetected = !digitalRead(RAIN_SENSOR_PIN);
  
  Serial.print("Rain Detected: ");
  Serial.println(rainDetected ? "YES" : "NO");
  
  return rainDetected;
}

// ==================== PUMP CONTROL ====================
void controlPump(bool state) {
  if (state) {
    // Turn pump ON
    digitalWrite(RELAY_PIN, HIGH);
    pumpActive = true;
    pumpStartTime = millis();
    Serial.println("Pump turned ON");
    
    // Publish pump status
    mqttClient.publish("agromind/pump/status", "ON");
    
  } else {
    // Turn pump OFF
    digitalWrite(RELAY_PIN, LOW);
    pumpActive = false;
    Serial.println("Pump turned OFF");
    
    // Publish pump status
    mqttClient.publish("agromind/pump/status", "OFF");
  }
}

// ==================== LED BLINK ====================
void blinkLED() {
  ledState = !ledState;
  digitalWrite(LED_PIN, ledState);
}

// ==================== DEBUG FUNCTIONS ====================
void printSensorReadings() {
  Serial.println("\n=== SENSOR READINGS ===");
  Serial.print("Soil Moisture: ");
  Serial.print(readSoilMoisture());
  Serial.println("%");
  
  Serial.print("Temperature: ");
  Serial.print(dht.readTemperature());
  Serial.println("°C");
  
  Serial.print("Humidity: ");
  Serial.print(dht.readHumidity());
  Serial.println("%");
  
  Serial.print("Light Level: ");
  Serial.print(readLightLevel());
  Serial.println(" (raw)");
  
  Serial.print("Rain Detected: ");
  Serial.println(readRainStatus() ? "YES" : "NO");
  
  Serial.print("Pump Status: ");
  Serial.println(pumpActive ? "ON" : "OFF");
  Serial.println("=====================\n");
}

/*
 * Additional Notes:
 * 
 * 1. Soil Moisture Calibration:
 *    - For best results, calibrate with your specific soil:
 *      - Take reading when sensor is in dry air: SOIL_DRY_VALUE
 *      - Take reading when sensor is in water: SOIL_WET_VALUE
 *    - Update SOIL_DRY_VALUE and SOIL_WET_VALUE accordingly
 * 
 * 2. Rain Sensor:
 *    - Typically active LOW (LOW when rain detected)
 *    - Using INPUT_PULLUP so we invert the reading
 *    - Adjust if your sensor works differently
 * 
 * 3. Pump Control:
 *    - Relay is active HIGH (HIGH = pump ON)
 *    - 180-second timeout prevents pump from running indefinitely
 *    - Can be controlled via MQTT or manually in code
 * 
 * 4. Power Considerations:
 *    - ESP32 + sensors + relay ≈ 150-200mA
 *    - Water pump can draw 300-800mA (12V)
 *    - Use separate power supply for pump
 * 
 * 5. Troubleshooting:
 *    - Check serial monitor at 115200 baud
 *    - Verify WiFi credentials
 *    - Check MQTT broker IP address
 *    - Ensure all sensors are properly connected
 */

// ==================== END OF FILE ====================