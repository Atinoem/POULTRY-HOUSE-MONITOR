#include <DHT.h>
#include <Wire.h> 
#include <LiquidCrystal_I2C.h>

// Initialize LCD at I2C address 0x27 for a 16x2 display
LiquidCrystal_I2C lcd(0x27, 16, 2);

// Sensor Pin Definitions
#define DHTPIN 2          // DHT22 Data pin connected to Digital Pin 2
#define DHTTYPE DHT22     // Using the DHT22 sensor
DHT dht(DHTPIN, DHTTYPE);

const int ldrPin = A0;    // Photoresistor (LDR) connected to Analog Pin A0

// Actuator Pin Definitions
const int fanPin = 3;     // Cooling Fan MOSFET connected to Pin 3
const int lightPin = 10;  // Heating Bulb MOSFET connected to Pin 10
const int buzzerPin = 5;  // Active Piezo Buzzer connected to Pin 5

// LED Indicator Pin Definitions
const int redLedPin = 6;    // High Temperature Alert LED (Overheating)
const int yellowLedPin = 7; // Low Temperature Alert LED (Too Cold)
const int greenLedPin = 8;  // Optimal Temperature LED (Comfortable Zone)

// Default Temperature Thresholds (Week 2 preset active by default: 29.0°C to 32.0°C)
float tempLowLimit = 29.0;
float tempHighLimit = 32.0;

// Track state of the heating bulb hysteresis
bool isBulbActive = false;

// Track active mode: 1 = WEEK1, 2 = WEEK2, 3 = WEEK3, 4 = WEEK4, 0 = MANUAL
int activeWeekMode = 2; 

// Absolute safety envelope for operator-supplied setpoints (degrees C)
const float SAFE_TEMP_MIN = 15.0;
const float SAFE_TEMP_MAX = 40.0;
const float MIN_TEMP_SPAN = 0.5;

// Default Light Threshold
int darkThreshold = 300; 

// Timing Variables (Non-blocking loop execution)
unsigned long lastSensorReadTime = 0;
const unsigned long sensorInterval = 2000; // DHT22 reads best at 2-second intervals

// Serial Buffer Variables
String inputBuffer = "";
const unsigned int MAX_COMMAND_LENGTH = 32;

void setup() {
  Serial.begin(9600);
  dht.begin();

  // Initialize LCD Screen
  lcd.init();
  lcd.backlight();
  lcd.clear();
  lcd.setCursor(0, 0);
  lcd.print("System Ready");
  delay(1000);
  lcd.clear();

  // Configure Actuators
  pinMode(fanPin, OUTPUT);
  pinMode(lightPin, OUTPUT);
  pinMode(buzzerPin, OUTPUT);
  
  digitalWrite(fanPin, LOW);
  digitalWrite(lightPin, LOW);
  digitalWrite(buzzerPin, LOW);

  // Configure LEDs
  pinMode(redLedPin, OUTPUT);
  pinMode(yellowLedPin, OUTPUT);
  pinMode(greenLedPin, OUTPUT);

  digitalWrite(redLedPin, LOW);
  digitalWrite(yellowLedPin, LOW);
  digitalWrite(greenLedPin, LOW);
}

void loop() {
  // 1. Process Incoming Serial Commands (Non-Blocking)
  while (Serial.available() > 0) {
    char inChar = (char)Serial.read();
    if (inChar == '\n') {
      processCommand(inputBuffer);
      inputBuffer = "";
    } else if (inChar != '\r') {
      if (inputBuffer.length() < MAX_COMMAND_LENGTH) {
        inputBuffer += inChar;
      } else {
        // Oversized command: drop it instead of exhausting SRAM
        inputBuffer = "";
      }
    }
  }

  // 2. Read Sensors and Update Controls at set intervals
  unsigned long currentMillis = millis();
  if (currentMillis - lastSensorReadTime >= sensorInterval) {
    lastSensorReadTime = currentMillis;

    // Read Physical Sensors
    float temperature = dht.readTemperature();
    float humidity = dht.readHumidity();
    int lightLevel = analogRead(ldrPin);

    // Guard against invalid sensor readings
    if (isnan(temperature) || isnan(humidity)) {
      temperature = 0.0;
      humidity = 0.0;
    }

    int fanStatus = 0;
    float tempMidPoint = (tempLowLimit + tempHighLimit) / 2.0;

    // 3. Heating Bulb Hysteresis Logic
    if (temperature < tempLowLimit) {
      isBulbActive = true; // Turn ON when below threshold
    } else if (temperature >= tempMidPoint) {
      isBulbActive = false; // Turn OFF once target average is reached
    }

    // 4. Actuator & LED Logic
    if (temperature > 0.0) {
      if (temperature > tempHighLimit) {
        // 🔴 OVERHEATING -> Fan ON, Red LED ON, Green & Yellow OFF
        digitalWrite(fanPin, HIGH);
        fanStatus = 1;

        digitalWrite(redLedPin, HIGH);
        digitalWrite(yellowLedPin, LOW);
        digitalWrite(greenLedPin, LOW);

        triggerBuzzerChirp(150);

      } else if (temperature < tempLowLimit) {
        // 🟡 TOO COLD -> Fan OFF, Yellow LED ON, Green & Red OFF
        digitalWrite(fanPin, LOW);
        fanStatus = 0;

        digitalWrite(redLedPin, LOW);
        digitalWrite(yellowLedPin, HIGH);
        digitalWrite(greenLedPin, LOW);

        triggerBuzzerDoubleChirp();

      } else {
        // 🟢 RANGE REACHED -> Fan OFF, Yellow & Red OFF, Green LED ON
        digitalWrite(fanPin, LOW);
        fanStatus = 0;

        digitalWrite(redLedPin, LOW);
        digitalWrite(yellowLedPin, LOW);
        digitalWrite(greenLedPin, HIGH);

        digitalWrite(buzzerPin, LOW);
      }
    }

    // 5. Apply Heating Bulb Relay State
    digitalWrite(lightPin, isBulbActive ? HIGH : LOW);

    // 6. Display Readings on 16x2 LCD
    // Line 1: Temperature & Humidity
    lcd.setCursor(0, 0);
    lcd.print("T:");
    lcd.print(temperature, 1);
    lcd.print((char)223); // Degree symbol °
    lcd.print("C H:");
    lcd.print(humidity, 0);
    lcd.print("%  ");

    // Line 2: Light level & Fan Status
    lcd.setCursor(0, 1);
    lcd.print("Lgt:");
    lcd.print(lightLevel);
    if (lightLevel < 100) lcd.print(" ");  // Formatting padding for numbers
    if (lightLevel < 10)  lcd.print(" ");
    
    lcd.print(" Fan:");
    lcd.print(fanStatus ? "ON " : "OFF");

    // 7. Output Data Stream for Streamlit Dashboard (CSV: Temp,Humidity,Light,Fan)
    Serial.print(temperature, 1);
    Serial.print(",");
    Serial.print(humidity, 1);
    Serial.print(",");
    Serial.print(lightLevel);
    Serial.print(",");
    Serial.println(fanStatus);
  }
}

// Handler for incoming commands from Streamlit / Python
void processCommand(String command) {
  command.trim();

  if (command.equals("WEEK1")) {
    tempLowLimit = 32.0; tempHighLimit = 35.0;
    activeWeekMode = 1;
  } else if (command.equals("WEEK2")) {
    tempLowLimit = 29.0; tempHighLimit = 32.0;
    activeWeekMode = 2;
  } else if (command.equals("WEEK3")) {
    tempLowLimit = 26.0; tempHighLimit = 29.0;
    activeWeekMode = 3;
  } else if (command.equals("WEEK4")) {
    tempLowLimit = 23.0; tempHighLimit = 26.0;
    activeWeekMode = 4;
  } else if (command.startsWith("SET_LOW:")) {
    float val = command.substring(8).toFloat();
    if (isSafeTemp(val) && tempHighLimit - val >= MIN_TEMP_SPAN) {
      tempLowLimit = val;
      activeWeekMode = 0; // Switching to manual mode
    }
  } else if (command.startsWith("SET_HIGH:")) {
    float val = command.substring(9).toFloat();
    if (isSafeTemp(val) && val - tempLowLimit >= MIN_TEMP_SPAN) {
      tempHighLimit = val;
      activeWeekMode = 0;
    }
  } else if (command.startsWith("SET_DARK:")) {
    int val = command.substring(9).toInt();
    if (val > 0 && val <= 1023) darkThreshold = val;
  }
}

bool isSafeTemp(float val) {
  return val >= SAFE_TEMP_MIN && val <= SAFE_TEMP_MAX;
}

// Helpers for audible feedback
void triggerBuzzerChirp(int duration) {
  digitalWrite(buzzerPin, HIGH);
  delay(duration);
  digitalWrite(buzzerPin, LOW);
}

void triggerBuzzerDoubleChirp() {
  digitalWrite(buzzerPin, HIGH);
  delay(80);
  digitalWrite(buzzerPin, LOW);
  delay(80);
  digitalWrite(buzzerPin, HIGH);
  delay(80);
  digitalWrite(buzzerPin, LOW);
}