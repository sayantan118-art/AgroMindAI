/*
 AgroMind AI - ESP32 Firmware
 Complete sensor monitoring and irrigation control system
*/

// ==================== LIBRARIES ====================
#include <WiFi.h>
#include <PubSubClient.h>
#include <ArduinoJson.h>
#include <DHT.h>
#include "secrets.h"  // WiFi + MQTT credentials — gitignored, never commit

// ==================== PIN DEFINITIONS ====================
#define SOIL_MOISTURE_PIN 34
#define DHT_PIN 16
#define RAIN_SENSOR_DO_PIN 18
#define RAIN_SENSOR_AO_PIN 32
#define LDR_PIN 35
#define RELAY_PIN 26
#define LED_PIN 2

// ==================== NETWORK CONFIG ====================
// All credentials are defined in secrets.h (gitignored)
// See secrets.h.example for the required format

// ==================== SENSOR CONFIG ====================
#define DHT_TYPE DHT22
#define SOIL_DRY_VALUE 4095
#define SOIL_WET_VALUE 1500

#define PUMP_TIMEOUT_MS 180000
#define PUBLISH_INTERVAL_MS 10000

// ==================== GLOBAL OBJECTS ====================
// TLS Client for HiveMQ Port 8883
#include <WiFiClientSecure.h>
WiFiClientSecure espClient;
PubSubClient mqttClient(espClient);
DHT dht(DHT_PIN, DHT_TYPE);

// ==================== GLOBAL VARIABLES ====================
unsigned long lastPublishTime = 0;
unsigned long lastReconnectAttempt = 0;
unsigned long pumpStartTime = 0;

bool pumpActive = false;
bool ledState = false;

// ==================== FUNCTION DECLARATIONS ====================
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

// ==================== SETUP ====================
void setup() {

  Serial.begin(115200);
  Serial.println("\nAgroMind ESP32 Starting...");

  analogReadResolution(12);

  pinMode(SOIL_MOISTURE_PIN, INPUT);
  pinMode(RAIN_SENSOR_DO_PIN, INPUT_PULLUP);
  pinMode(LDR_PIN, INPUT);
  pinMode(RELAY_PIN, OUTPUT);
  pinMode(LED_PIN, OUTPUT);

  digitalWrite(RELAY_PIN, LOW);
  digitalWrite(LED_PIN, LOW);

  dht.begin();

  espClient.setInsecure(); // Required for HiveMQ TLS
  setupWiFi();
  setupMQTT();

  Serial.println("Setup Complete");
}

// ==================== MAIN LOOP ====================
void loop() {

  unsigned long currentMillis = millis();

  if (!mqttClient.connected()) {
    reconnectMQTT();
  }

  mqttClient.loop();

  if (currentMillis - lastPublishTime >= PUBLISH_INTERVAL_MS) {

    publishSensorData();

    lastPublishTime = currentMillis;
    blinkLED();
  }

  if (pumpActive && (currentMillis - pumpStartTime >= PUMP_TIMEOUT_MS)) {

    Serial.println("Pump timeout reached");
    controlPump(false);
  }

  delay(10);
}

// ==================== WIFI ====================
void setupWiFi() {

  Serial.print("Connecting to WiFi ");

  WiFi.begin(WIFI_SSID, WIFI_PASS);

  while (WiFi.status() != WL_CONNECTED) {

    delay(500);
    Serial.print(".");
  }

  Serial.println();
  Serial.println("WiFi Connected");

  Serial.print("IP: ");
  Serial.println(WiFi.localIP());
}

// ==================== MQTT ====================
void setupMQTT() {

  mqttClient.setServer(MQTT_BROKER, MQTT_PORT);
  mqttClient.setCallback(mqttCallback);
  mqttClient.setBufferSize(1024);
}

void reconnectMQTT() {

  unsigned long currentMillis = millis();

  if (currentMillis - lastReconnectAttempt < 5000) return;

  lastReconnectAttempt = currentMillis;

  Serial.print("Attempting MQTT connection...");

  String clientId = "AgroMindESP32-";
  clientId += String(random(0xffff), HEX);

  if (mqttClient.connect(clientId.c_str(), MQTT_USER, MQTT_PASS)) {

    Serial.println("connected");

    mqttClient.subscribe("agromind/pump");

  } else {

    Serial.print("failed rc=");
    Serial.println(mqttClient.state());
  }
}

// ==================== MQTT CALLBACK ====================
void mqttCallback(char* topic, byte* payload, unsigned int length) {

  String message;

  for (unsigned int i = 0; i < length; i++) {
    message += (char)payload[i];
  }

  Serial.print("MQTT Message: ");
  Serial.println(message);

  if (String(topic) == "agromind/pump") {

    if (message == "ON") controlPump(true);
    if (message == "OFF") controlPump(false);
  }
}

// ==================== PUBLISH SENSOR DATA ====================
void publishSensorData() {

  float soilMoisture = readSoilMoisture();
  float temperature = dht.readTemperature();
  float humidity = dht.readHumidity();
  float lightLevel = readLightLevel();
  bool rainDetected = readRainStatus();

  if (isnan(temperature) || isnan(humidity)) {

    Serial.println("DHT Error");

    temperature = 25;
    humidity = 60;
  }

  StaticJsonDocument<256> doc;

  doc["soil"] = soilMoisture;
  doc["temp"] = temperature;
  doc["hum"] = humidity;
  doc["light"] = lightLevel;
  doc["rain"] = rainDetected;
  doc["pump"] = pumpActive;

  char buffer[256];
  serializeJson(doc, buffer);

  if (mqttClient.publish("agromind/sensors", buffer)) {

    Serial.println(buffer);

  } else {

    Serial.println("MQTT publish failed");
  }
}

// ==================== SENSOR FUNCTIONS ====================
float readSoilMoisture() {

  int raw = analogRead(SOIL_MOISTURE_PIN);

  float percent = map(raw, SOIL_DRY_VALUE, SOIL_WET_VALUE, 0, 100);
  percent = constrain(percent, 0, 100);

  Serial.print("Soil: ");
  Serial.println(percent);

  return percent;
}

float readLightLevel() {

  int raw = analogRead(LDR_PIN);

  Serial.print("Light: ");
  Serial.println(raw);

  return raw;
}

bool readRainStatus() {

  bool rain = !digitalRead(RAIN_SENSOR_DO_PIN);

  Serial.print("Rain: ");
  Serial.println(rain);

  return rain;
}

// ==================== PUMP CONTROL ====================
void controlPump(bool state) {

  if (state) {

    digitalWrite(RELAY_PIN, HIGH);
    pumpActive = true;
    pumpStartTime = millis();

    Serial.println("Pump ON");

  } else {

    digitalWrite(RELAY_PIN, LOW);
    pumpActive = false;

    Serial.println("Pump OFF");
  }
}

// ==================== LED ====================
void blinkLED() {

  ledState = !ledState;
  digitalWrite(LED_PIN, ledState);
}