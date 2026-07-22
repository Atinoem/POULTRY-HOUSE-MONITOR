#include <DHT.h>

// Sensor Pin Definitions
#define DHTPIN 2          // DHT22 Data pin connected to Digital Pin 2
#define DHTTYPE DHT22     // Using the DHT22 sensor
DHT dht(DHTPIN, DHTTYPE);

const int ldrPin = A0;    // Photoresistor (LDR) connected to Analog Pin A0

// Actuator Pin Definition
const int fanPin = 3;     // Single MOSFET module connected to Pin 3

// Dynamic Temperature Threshold (dynamically updated by your Streamlit App selection)
float tempHighLimit = 32.0; // Default: Week 2 threshold is 32.0°C

void setup() {
  // Initialize Serial communication at 9600 baud rate
  Serial.begin(9600);
  
  // Initialize DHT sensor
  dht.begin();
  
  // Configure the single MOSFET control pin as an OUTPUT
  pinMode(fanPin, OUTPUT);
  digitalWrite(fanPin, LOW); // Start with the fan OFF
}

void loop() {
  // 1. Check for incoming threshold updates from Python Dashboard FIRST
  // Streamlit sends: "SET:high_limit\n"
  if (Serial.available() > 0) {
    String incoming = Serial.readStringUntil('\n');
    incoming.trim();
    
    if (incoming.startsWith("SET:")) {
      String valueStr = incoming.substring(4);
      float newThreshold = valueStr.toFloat();
      // Ensure we parsed a valid positive number before updating
      if (newThreshold > 0.0) {
        tempHighLimit = newThreshold;
      }
    }
  }

  // 2. Read physical values from the sensors
  float temperature = dht.readTemperature();
  float humidity = dht.readHumidity();
  int lightLevel = analogRead(ldrPin); // Reads 0 (dark) to 1023 (bright)

  // Check if DHT22 read failed
  if (isnan(temperature) || isnan(humidity)) {
    temperature = 0.0;
    humidity = 0.0;
  }

  // 3. Control Logic for the single MOSFET module based on dynamic threshold
  int fanStatus = 0;
  if (temperature > tempHighLimit) {
    digitalWrite(fanPin, HIGH); // Turn fan ON (Cooldown)
    fanStatus = 1;
  } else {
    digitalWrite(fanPin, LOW);  // Turn fan OFF (Comfortable temperature)
    fanStatus = 0;
  }

  // 4. Print cleanly formatted data for the Python Dashboard to parse
  // Format: Temperature,Humidity,Light_Level,Fan_Status
  Serial.print(temperature, 1);
  Serial.print(",");
  Serial.print(humidity, 1);
  Serial.print(",");
  Serial.print(lightLevel);
  Serial.print(",");
  Serial.println(fanStatus);

  // 2-second interval before repeating the loop
  delay(2000);
}