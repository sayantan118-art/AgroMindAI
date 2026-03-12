# AgroMind AI — MQTT Broker Migration Guide

## Current State
The ESP32 firmware connects to a **local Mosquitto broker** at a hardcoded IP address (`10.21.34.128:1883`). This breaks when:
- The demo machine moves to a different network
- The backend is running on Render (cloud) and needs remote MQTT access
- IP addresses change between hotspot sessions

## Recommended Migration: HiveMQ Cloud (Free Tier)

HiveMQ Cloud provides a free, always-on cloud MQTT broker with TLS support — ideal for this project.

### Step 1: Create a HiveMQ Cloud Account

1. Go to [https://www.hivemq.com/mqtt-cloud-broker/](https://www.hivemq.com/mqtt-cloud-broker/)
2. Sign up for free
3. Create a new cluster (free tier: 100 connections, no expiry)
4. Note your broker URL: `your-cluster.s2.eu.hivemq.cloud`

### Step 2: Create MQTT Credentials

In the HiveMQ Cloud console:
1. Go to **Access Management**
2. Create a user for the ESP32: `agromind_esp32` / `<strong-password>`
3. Create a user for n8n: `agromind_n8n` / `<strong-password>`

### Step 3: Update ESP32 Firmware

In `agromind_esp32.ino`, update the Network Config section:

```cpp
// ==================== NETWORK CONFIG ====================
#define WIFI_SSID "Your_WiFi_SSID"
#define WIFI_PASS "Your_WiFi_Password"

#define MQTT_BROKER "your-cluster.s2.eu.hivemq.cloud"
#define MQTT_PORT 8883        // TLS port (not 1883)
#define MQTT_USER "agromind_esp32"
#define MQTT_PASS "your_mqtt_password"
```

Also update the library includes and WiFi client to use TLS:

```cpp
#include <WiFiClientSecure.h>   // Add this
WiFiClientSecure espClient;     // Use Secure instead of WiFiClient

// In setupMQTT():
espClient.setInsecure();        // For demo; use setCACert() for production
mqttClient.setServer(MQTT_BROKER, MQTT_PORT);

// In reconnectMQTT():
if (mqttClient.connect(clientId.c_str(), MQTT_USER, MQTT_PASS)) {
```

### Step 4: Update n8n MQTT Credentials

In n8n → Credentials → MQTT:
- Protocol: `mqtts://` (TLS)
- Host: `your-cluster.s2.eu.hivemq.cloud`
- Port: `8883`
- Username: `agromind_n8n`
- Password: `<your-password>`
- SSL: Enabled

### Step 5: Verify Connection

After flashing firmware and updating n8n:
1. Open Serial Monitor (115200 baud) — should see "MQTT connected"
2. In n8n, manually trigger the Main CPS Loop
3. Check HiveMQ Cloud console → Live Data to see messages flowing

## MQTT Topic Reference

| Topic | Direction | Payload | Description |
|-------|-----------|---------|-------------|
| `agromind/sensors` | ESP32 → Cloud | `{"soil":45.2,"temp":28.1,"hum":65.0,"light":2048,"rain":false,"pump":false}` | Sensor data every 10s |
| `agromind/pump` | Cloud → ESP32 | `{"action":"ON","duration_sec":120}` | Pump control command |
| `agromind/pump/status` | ESP32 → Cloud | `{"active":true,"elapsed_sec":45}` | Pump feedback |
| `agromind/alerts` | Cloud → Dashboard | `{"severity":"warning","message":"..."}` | Health alerts |
| `agromind/heartbeat` | ESP32 → Cloud | `{"uptime_ms":360000,"wifi_rssi":-62}` | Liveness ping |

## Local Mosquitto (Fallback)

If staying on local Mosquitto for the demo, ensure:
1. The n8n machine and ESP32 are on the **same WiFi network**
2. Mosquitto is bound to `0.0.0.0` (not just localhost)
3. The MQTT broker IP in firmware matches the machine running Mosquitto

Check `mosquitto.conf`:
```
listener 1883 0.0.0.0
allow_anonymous true
```
