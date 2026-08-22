# 🐔 CoopGuard™ – Smart Poultry House Monitoring & Control System

CoopGuard™ is an IoT-based poultry house monitoring and control system designed to automate environmental management inside poultry brooders. The system continuously monitors temperature, humidity, and light intensity, then automatically controls heating and cooling devices to maintain optimal conditions for healthy chick growth.

## Features

- 🌡️ Real-time temperature and humidity monitoring (DHT22)
- 💡 Light intensity monitoring (LDR)
- 🔥 Automatic heating bulb control
- 🌬️ Automatic cooling fan control
- 📟 16×2 I2C LCD live display
- 🚨 LED and buzzer alerts for abnormal conditions
- 📊 Python Streamlit dashboard for live monitoring
- 📈 Historical temperature and humidity graphs
- 🔄 Two-way serial communication between Arduino and dashboard
- 🐣 Week-based temperature profiles (Week 1–4)

## Hardware

- Arduino Uno
- DHT22 Temperature & Humidity Sensor
- LDR Light Sensor
- 16×2 I2C LCD
- Cooling Fan
- Heating Bulb
- MOSFET Driver Circuit
- LEDs
- Piezo Buzzer

## Software

- Arduino IDE (C++)
- Python
- Streamlit
- PySerial

## How It Works

1. Sensors continuously collect environmental data.
2. Arduino compares readings with the selected chick growth stage.
3. Heating or cooling is automatically activated when needed.
4. Data is displayed on both the LCD and Streamlit dashboard.
5. Users can monitor the system and adjust settings from the dashboard.

## Project Structure

```
Arduino/
    Arduino source code

Dashboard/
    Streamlit application

Docs/
    Technical report

README.md
```

## Security Notes

The dashboard can switch the heating bulb and cooling fan, so treat it as a control system, not a read-only display:

- Set a dashboard password before starting Streamlit; without one the app runs unauthenticated and warns in the sidebar:
  ```
  export COOPGUARD_DASHBOARD_PASSWORD="choose-a-strong-password"
  streamlit run Dashboard.py --server.address 127.0.0.1
  ```
  Alternatively put `dashboard_password = "..."` in `.streamlit/secrets.toml` (never commit that file).
- Keep the dashboard bound to localhost or behind a VPN/reverse proxy with TLS; do not expose it directly to the internet.
- Setpoints are clamped to 15–40 °C and validated both in the dashboard and in the Arduino firmware, so a bad or malicious command cannot drive the brooder to a lethal target.

## Future Improvements

- Wi-Fi / MQTT cloud connectivity
- SMS and email alerts
- Remote monitoring over the Internet
- Feed and water level monitoring
- Long-term data storage
- Air quality and ammonia sensing
- Solar or battery backup support

## Contributors

- Emily Atino
- Roland Emma Watega
- Lodu Samson Lomundu
- Stephen Cyrus Kalema
- Nalubega Melissa V

## License

This project was developed as part of the **CSC1304 Practical Skills Development** course and is intended for educational purposes.