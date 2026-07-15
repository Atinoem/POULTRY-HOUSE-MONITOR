#include <DHT.h>

// Sensor Pin Definitions
#define DHTPIN 2          // DHT22 Data pin connected to Digital Pin 2
#define DHTTYPE DHT22     // Using the DHT22 sensor
DHT dht(DHTPIN, DHTTYPE);

const int ldrPin = A0;    // Photoresistor (LDR) connected to Analog Pin A0

// Actuator Pin Definition
const int fanPin = 3;     // MOSFET control pin connected to Digital Pin 3

// Temperature Threshold for Fan Activation
const float TEMP_THRESHOLD = 30.0; // Fan turns on when temp is above 30.0°C

void setup() {
  // Initialize Serial communication at 9600 baud rate
  Serial.begin(9600);
  
  // Initialize DHT sensor
  dht.begin();
  
  // Configure the MOSFET control pin as an OUTPUT
  pinMode(fanPin, OUTPUT);
  digitalWrite(fanPin, LOW); // Start with the fan OFF
}

void loop() {
  // Read values from the DHT22
  float temperature = dht.readTemperature();
  float humidity = dht.readHumidity();
  
  // Read analog value from the Photoresistor (0 to 1023)
  int lightLevel = analogRead(ldrPin);

  // Check if DHT22 read failed (isnan stands for "is Not a Number")
  if (isnan(temperature) || isnan(humidity)) {
    Serial.println("Failed to read from DHT22 sensor!");
  } else {
    // Print reading results to the Serial Monitor
    Serial.print("Temp: ");
    Serial.print(temperature);
    Serial.print(" °C | Humidity: ");
    Serial.print(humidity);
    Serial.print(" % | Light: ");
    Serial.print(lightLevel);

    // --- Fan Control Logic ---
    if (temperature > TEMP_THRESHOLD) {
      digitalWrite(fanPin, HIGH); // Send 5V to the MOSFET SIG pin to turn fan ON
      Serial.println(" | Fan Status: ON");
    } else {
      digitalWrite(fanPin, LOW);  // Send 0V to the MOSFET SIG pin to turn fan OFF
      Serial.println(" | Fan Status: OFF");
    }
  }

  // Wait 2 seconds before taking the next reading
  delay(2000);
}