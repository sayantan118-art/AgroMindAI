# AgroMind AI - Complete Hardware Shopping List

## Project Analysis Summary
Based on the backend API (`main.py`), n8n workflows, and dashboard requirements, the system monitors:
- Soil moisture (capacitive sensor)
- Temperature & Humidity (DHT22 sensor)
- Rain detection (rain sensor module)
- Pump control via relay

The system uses MQTT for communication between ESP32 and the backend server.

---

## 🛒 MAIN COMPONENTS

| # | Component | Model/Spec | ESP32 Pin | Qty | Price (INR) | Buy From | Notes |
|---|-----------|------------|-----------|-----|-------------|----------|-------|
| 1 | **Microcontroller** | ESP32 DevKit V1 (30-pin) | - | 1 | ₹450-550 | Amazon, Robu.in | WiFi + Bluetooth, 3.3V logic |
| 2 | **Soil Moisture Sensor** | Capacitive v1.2 (Corrosion-resistant) | GPIO 34 (ADC1_CH6) | 1 | ₹150-200 | Robu.in, Amazon | Analog output, 3.3-5V |
| 3 | **Temperature & Humidity** | DHT22 (AM2302) | GPIO 4 | 1 | ₹250-350 | Amazon, Robu.in | Digital, ±0.5°C accuracy |
| 4 | **Rain Sensor Module** | YL-83 Rain Sensor | GPIO 35 (ADC1_CH7) | 1 | ₹80-120 | Robu.in, Amazon | Analog + Digital output |
| 5 | **Relay Module** | 5V 1-Channel Relay (Optocoupler) | GPIO 26 | 1 | ₹80-120 | Amazon, Robu.in | For pump control, 10A max |
| 6 | **Water Pump** | 12V DC Submersible Pump (3-6L/min) | Via Relay | 1 | ₹300-500 | Amazon, Flipkart | Mini water pump |
| 7 | **Power Supply** | 12V 2A DC Adapter | - | 1 | ₹200-300 | Amazon, Local | For pump + ESP32 |
| 8 | **Voltage Regulator** | LM2596 Buck Converter (12V→5V) | - | 1 | ₹80-120 | Robu.in, Amazon | Step down 12V to 5V for ESP32 |

**Subtotal (Main Components): ₹1,590 - ₹2,260**

---

## 🔌 WIRING & CONNECTIONS

| # | Component | Model/Spec | Qty | Price (INR) | Buy From | Notes |
|---|-----------|------------|-----|-------------|----------|-------|
| 9 | **Breadboard** | 830-point Half-size | 1 | ₹80-120 | Amazon, Robu.in | For prototyping |
| 10 | **Jumper Wires** | Male-to-Male (40pcs) | 1 pack | ₹50-80 | Amazon, Robu.in | 20cm length |
| 11 | **Jumper Wires** | Male-to-Female (40pcs) | 1 pack | ₹50-80 | Amazon, Robu.in | For sensor connections |
| 12 | **Micro USB Cable** | 1m Data Cable | 1 | ₹50-100 | Amazon, Local | For ESP32 programming |
| 13 | **DC Power Jack** | 5.5mm x 2.1mm Female | 2 | ₹20-40 | Robu.in, Amazon | For power connections |
| 14 | **Screw Terminals** | 2-pin 5mm pitch | 5 | ₹30-50 | Robu.in, Amazon | For secure connections |

**Subtotal (Wiring): ₹280 - ₹470**

---

## 🔧 TOOLS & ACCESSORIES

| # | Item | Specification | Qty | Price (INR) | Buy From | Required? |
|---|------|---------------|-----|-------------|----------|-----------|
| 15 | **Soldering Iron Kit** | 25W with stand + solder wire | 1 | ₹300-500 | Amazon, Local | Optional (for permanent) |
| 16 | **Multimeter** | Digital DT830B | 1 | ₹200-350 | Amazon, Robu.in | Recommended |
| 17 | **Wire Stripper** | 0.2-6mm² | 1 | ₹150-250 | Amazon, Local | Recommended |
| 18 | **Heat Shrink Tubing** | Assorted sizes (100pcs) | 1 pack | ₹100-150 | Amazon, Robu.in | Optional |
| 19 | **Electrical Tape** | PVC Insulation Tape | 1 roll | ₹30-50 | Local, Amazon | Required |
| 20 | **Cable Ties** | 100mm (100pcs) | 1 pack | ₹50-80 | Amazon, Local | Recommended |

**Subtotal (Tools): ₹830 - ₹1,380**

---

## 📦 ENCLOSURE & PROTECTION

| # | Item | Specification | Qty | Price (INR) | Buy From | Notes |
|---|------|---------------|-----|-------------|----------|-------|
| 21 | **Waterproof Box** | IP65 ABS 150x110x70mm | 1 | ₹250-400 | Amazon, Robu.in | For ESP32 + relay |
| 22 | **Cable Glands** | PG7 (3-6.5mm) | 4 | ₹40-80 | Amazon, Robu.in | Waterproof cable entry |
| 23 | **Silica Gel Packets** | 10g (10pcs) | 1 pack | ₹50-100 | Amazon | Moisture protection |
| 24 | **Mounting Tape** | 3M Double-sided foam | 1 roll | ₹80-120 | Amazon, Local | For sensor mounting |

**Subtotal (Enclosure): ₹420 - ₹700**

---

## 💡 OPTIONAL UPGRADES

| # | Component | Model/Spec | ESP32 Pin | Qty | Price (INR) | Buy From | Purpose |
|---|-----------|------------|-----------|-----|-------------|----------|---------|
| 25 | **OLED Display** | 0.96" I2C 128x64 | SDA: GPIO 21, SCL: GPIO 22 | 1 | ₹200-300 | Amazon, Robu.in | Local status display |
| 26 | **Light Sensor** | BH1750 (I2C) | SDA: GPIO 21, SCL: GPIO 22 | 1 | ₹150-200 | Robu.in, Amazon | Light level monitoring |
| 27 | **Battery Backup** | 18650 Li-ion + Holder | - | 2 cells | ₹400-600 | Amazon | Power backup |
| 28 | **Solar Panel** | 6V 2W with charge controller | - | 1 | ₹350-500 | Amazon, Robu.in | Solar power option |
| 29 | **Status LEDs** | 5mm Red/Green/Blue | GPIO 25, 27, 32 | 3 | ₹10-20 | Local, Robu.in | Visual indicators |
| 30 | **Buzzer** | 5V Active Buzzer | GPIO 33 | 1 | ₹30-50 | Robu.in, Amazon | Audio alerts |

**Subtotal (Optional): ₹1,140 - ₹1,670**

---

## 📊 TOTAL COST SUMMARY

| Category | Minimum (INR) | Maximum (INR) |
|----------|---------------|---------------|
| Main Components | ₹1,590 | ₹2,260 |
| Wiring & Connections | ₹280 | ₹470 |
| Tools & Accessories | ₹830 | ₹1,380 |
| Enclosure & Protection | ₹420 | ₹700 |
| **TOTAL (Essential)** | **₹3,120** | **₹4,810** |
| Optional Upgrades | ₹1,140 | ₹1,670 |
| **GRAND TOTAL (All)** | **₹4,260** | **₹6,480** |

---

## 🔌 PIN MAPPING REFERENCE

### ESP32 DevKit V1 Pin Assignments

```
┌─────────────────────────────────┐
│         ESP32 DevKit V1         │
├─────────────────────────────────┤
│ GPIO 34 ← Soil Moisture (Analog)│
│ GPIO 35 ← Rain Sensor (Analog)  │
│ GPIO 4  ← DHT22 (Data)          │
│ GPIO 26 → Relay (Control)       │
│ GPIO 21 ↔ I2C SDA (Optional)    │
│ GPIO 22 ↔ I2C SCL (Optional)    │
│ GPIO 25 → LED Red (Optional)    │
│ GPIO 27 → LED Green (Optional)  │
│ GPIO 32 → LED Blue (Optional)   │
│ GPIO 33 → Buzzer (Optional)     │
│ 3.3V    → DHT22 VCC             │
│ 5V      → Relay VCC             │
│ GND     → All GND connections   │
└─────────────────────────────────┘
```

### Sensor Connections Detail

**1. Capacitive Soil Moisture Sensor**
- VCC → ESP32 3.3V
- GND → ESP32 GND
- AOUT → ESP32 GPIO 34 (ADC1_CH6)

**2. DHT22 Temperature & Humidity**
- VCC → ESP32 3.3V
- GND → ESP32 GND
- DATA → ESP32 GPIO 4 (with 10kΩ pull-up resistor to 3.3V)

**3. Rain Sensor Module**
- VCC → ESP32 3.3V
- GND → ESP32 GND
- AO (Analog) → ESP32 GPIO 35 (ADC1_CH7)
- DO (Digital) → Not used

**4. Relay Module (Pump Control)**
- VCC → ESP32 5V (or external 5V)
- GND → ESP32 GND
- IN → ESP32 GPIO 26
- COM → 12V Power Supply (+)
- NO (Normally Open) → Water Pump (+)
- Water Pump (-) → 12V Power Supply (-)

**5. Power Distribution**
- 12V Adapter → Buck Converter Input
- Buck Converter Output (5V) → ESP32 VIN
- 12V Adapter → Relay COM terminal
- ESP32 GND → Common Ground for all components

---

## 🛍️ WHERE TO BUY IN INDIA

### Online Stores

1. **Robu.in** (Best for electronics components)
   - Website: https://robu.in
   - Specializes in robotics and IoT components
   - Good prices, reliable delivery
   - Recommended for: Sensors, ESP32, relay modules

2. **Amazon India** (Fast delivery, easy returns)
   - Website: https://amazon.in
   - Search: "ESP32 DevKit", "DHT22 sensor", "soil moisture sensor"
   - Prime delivery available
   - Recommended for: All components, tools

3. **ElectronicsComp.com**
   - Website: https://electronicscomp.com
   - Wide range of development boards
   - Bulk discounts available

4. **Flipkart** (Alternative to Amazon)
   - Good for pumps and power supplies
   - Competitive pricing

### Local Stores (Major Cities)

- **Delhi**: Lajpat Rai Market, Nehru Place
- **Mumbai**: Lamington Road
- **Bangalore**: SP Road
- **Kolkata**: Chandni Chowk Electronics Market
- **Chennai**: Ritchie Street

---

## 📝 ASSEMBLY NOTES

### Soldering Required?
- **For Prototyping**: NO - Use breadboard and jumper wires
- **For Permanent Installation**: YES - Solder connections for reliability
- **Recommended**: Start with breadboard, solder after testing

### Breadboard Layout Tips
1. Place ESP32 in center of breadboard
2. Keep power rails organized (red = +, blue = -)
3. Group sensors on one side, relay on other
4. Use color-coded wires (red = power, black = ground, others = signals)

### Waterproofing Strategy
1. ESP32 + Relay → Inside waterproof box
2. Sensors → Outside, use cable glands for wires
3. Apply silicone sealant around cable gland threads
4. Add silica gel packets inside box
5. Mount box above ground level

### Power Considerations
- ESP32 draws ~80-160mA (WiFi active)
- DHT22 draws ~1-2mA
- Soil moisture sensor draws ~5-20mA
- Relay draws ~15-20mA
- Water pump draws ~300-800mA (12V)
- **Total**: ~1A peak (use 2A adapter for safety margin)

---

## 🔍 COMPONENT SELECTION TIPS

### ESP32 Board
- Choose DevKit V1 (30-pin) for more GPIO options
- Avoid NodeMCU-32S (fewer pins)
- Check for CP2102 or CH340 USB chip (both work fine)

### Soil Moisture Sensor
- **Capacitive > Resistive** (corrosion-resistant)
- Look for v1.2 or v2.0 (improved accuracy)
- Avoid cheap resistive probes (rust quickly)

### DHT Sensor
- **DHT22 > DHT11** (better accuracy: ±0.5°C vs ±2°C)
- AM2302 is DHT22 with built-in pull-up resistor
- Comes with or without PCB module (both work)

### Relay Module
- Choose optocoupler-isolated relay (safer)
- 5V trigger voltage (ESP32 compatible)
- 10A rating sufficient for small pumps
- Active LOW or HIGH (check datasheet, adjust code)

### Water Pump
- 12V DC submersible type
- 3-6 L/min flow rate for small gardens
- Check max head height (vertical lift capability)
- Food-grade if used for drinking water systems

---

## ⚠️ SAFETY WARNINGS

1. **Electrical Safety**
   - Never work on live circuits
   - Use proper insulation for 12V connections
   - Keep water away from electronics

2. **Water Protection**
   - Use IP65 or higher rated enclosures
   - Seal all cable entries properly
   - Test waterproofing before field deployment

3. **Sensor Placement**
   - Soil moisture sensor: Insert 2-3 inches deep
   - Rain sensor: Mount at 45° angle, facing up
   - DHT22: Keep in shade, good airflow

4. **Pump Safety**
   - Never run pump dry (damages motor)
   - Use check valve to prevent backflow
   - Add water level sensor if using tank

---

## 📚 ADDITIONAL RESOURCES

### Arduino Libraries Required
- **DHT sensor library** by Adafruit
- **PubSubClient** by Nick O'Leary (MQTT)
- **ArduinoJson** by Benoit Blanchon
- **WiFi** (built-in with ESP32 core)

### ESP32 Board Manager URL
```
https://raw.githubusercontent.com/espressif/arduino-esp32/gh-pages/package_esp32_index.json
```

### Firmware Code Location
- Not included in current repository
- Needs to be created based on pin mappings above
- Should publish to MQTT topic: `agromind/sensors`
- Should subscribe to MQTT topic: `agromind/pump`

---

## 🎯 RECOMMENDED PURCHASE ORDER

### Phase 1: Core System (₹2,000-2,500)
1. ESP32 DevKit V1
2. Soil Moisture Sensor (Capacitive)
3. DHT22 Sensor
4. Relay Module
5. Breadboard + Jumper Wires
6. Micro USB Cable

### Phase 2: Power & Pump (₹500-800)
7. 12V DC Pump
8. 12V 2A Power Adapter
9. Buck Converter

### Phase 3: Protection (₹400-700)
10. Waterproof Enclosure
11. Cable Glands
12. Mounting Hardware

### Phase 4: Optional Enhancements (₹1,000-1,500)
13. Rain Sensor
14. OLED Display
15. Light Sensor
16. Tools (if not owned)

---

**Generated for**: AgroMind AI Project  
**Date**: March 6, 2026  
**Based on**: backend/main.py, workflow-main.json, dashboard requirements  
**Currency**: Indian Rupees (INR)  
**Prices**: Approximate as of March 2026, may vary by vendor and location
