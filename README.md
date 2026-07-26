# POULTRY-HOUSE-MONITOR
 
CoopGuard™
Smart Poultry House • Healthy Birds • Better Yield
An Embedded IoT System for Automated Brooder Microclimate Management
TECHNICAL PROJECT REPORT
Project Title	CoopGuard™ — Smart Poultry House Monitoring & Control System
Prepared By	Group 19
Program	Embedded Systems Project
Supervisor	Dr. Lillian Muyama
Repository 	https://github.com/Atinoem/POULTRY-HOUSE-MONITOR.git
 1. Executive Summary
CoopGuard™ is an embedded Internet of Things (IoT) system developed to automate the management of the microclimate inside a poultry brooder house, where day-old and young chicks are raised during the most sensitive stage of their growth. At this stage, chicks are unable to regulate their own body temperature, making it essential to maintain the brooder temperature within a specific range that changes with their age. If the temperature falls below the recommended level, chicks may experience chilling, huddling, and increased mortality. Conversely, excessively high temperatures can lead to heat stress, reduced feed intake, dehydration, panting and, in severe cases death. Traditionally, maintaining these conditions requires constant manual monitoring, which is both labor-intensive and susceptible to human error. CoopGuard™ is designed to address this challenge by providing an automated and reliable monitoring and control solution.
The system combines a low-cost Arduino-based embedded controller, running the firmware contained in Day4.ino, with a Python/Streamlit web dashboard (CoopGuard/Dashboard.py) that enables real-time monitoring and remote control. The Arduino continuously reads data from a DHT22 sensor to measure temperature and humidity, while an LDR monitors the ambient light level. Based on the selected chick-age temperature range, the controller automatically switches a cooling fan and a heating bulb on or off through MOSFET circuitry whenever the measured temperature moves outside the desired limits. To keep users informed locally, the system includes a 16×2 I²C LCD, tri-colour LED indicators, and an active piezo buzzer. At the same time, the Streamlit dashboard displays live sensor readings, historical trends, and browser-based audible alerts, allowing farmers or supervisors to monitor the brooder remotely.
From an architectural perspective, CoopGuard™ demonstrates a complete sense–decide–actuate–visualise workflow. Environmental data is first collected by the embedded controller, which processes the readings and makes automatic control decisions to maintain suitable brooding conditions. The controller then streams telemetry data over a USB serial connection to the Python/Streamlit application, where the information is presented through an intuitive dashboard. The dashboard also allows users to send updated threshold values and operating-mode commands back to the controller, creating a continuous feedback loop between automated control and human supervision. This integration of embedded hardware with modern software provides the project's main engineering contribution, delivering a practical, low-cost solution for intelligent poultry brooder management.

2. System Architecture & Block Diagram Description
CoopGuard™ is built around two interconnected components. The Hardware (Embedded) Tier handles real-time environmental monitoring and automatically controls devices such as the heating bulb and cooling fan to maintain safe brooding conditions. The Software Tier focuses on presenting the collected data through an interactive dashboard, displaying historical trends, and allowing users to adjust system settings remotely. The two components communicate through a two-way serial connection: sensor data are continuously sent from the embedded hardware to the dashboard, while updated operating modes and temperature thresholds are sent back to the controller. This bidirectional communication enables both autonomous operation and effective human supervision.
2.1 Hardware Tier
Component	Interface / Pin	Function
DHT22 Sensor	Digital Pin 2	Combined temperature & relative-humidity sensing; sampled every 2 seconds (sensor's minimum stable sampling interval).
LDR (Photoresistor)	Analog Pin A0	Measures ambient light level (0–1023) inside the brooder, used for future lighting-schedule logic and dashboard telemetry.
Fan MOSFET	Digital Pin 3	Switches the cooling fan; engaged automatically during overheating events.
Heating Bulb MOSFET	Digital Pin 10	Switches the brooder heat lamp; engaged automatically during low-temperature events (age-mode dependent).
Active Piezo Buzzer	Digital Pin 5	Audible on-site alarm; short chirp on overheats, double-chirp pattern on under-temperature.
Status LEDs (Red/Yellow/Green)	Digital Pins 6 / 7 / 8	Instant visual indication of Overheating / Too Cold / Optimal zone respectively.
16×2 I²C LCD	I²C bus (address 0x27)	On-site display of live temperature, humidity, light level, and fan state for technicians without a laptop or phone.
2.2 Software & IoT Tier
The software tier is implemented in Python using the Streamlit web-application framework. As implemented in Dashboard.py, the pipeline is:
•	Serial CSV Streaming — the Arduino firmware writes one CSV line every 2 seconds in the form Temperature,Humidity,Light_Level,Fan_Status over USB serial at 9600 baud.
•	Python Serial Gateway (in-process) — a background SerialManager class inside Dashboard.py opens the COM/tty port using pyserial, runs a daemon thread (_serial_read_loop) that parses each CSV line, and stores the last 50 samples in a thread-safe deque. This class also issues outbound commands (WEEK1–WEEK4, SET_LOW:/SET_HIGH:) back to the Arduino, so it functions as the project's serial gateway even though it is not a standalone script.
•	Streamlit Frontend — renders live metric cards, Altair trend charts, and a scrolling telemetry log, auto-refreshing every 2 seconds via st.fragment(run_every=2).
It should be noted for engineering accuracy that the delivered source code does not yet include an Adafruit IO cloud broker integration or a separately deployed Python gateway process — there is no MQTT/HTTP client library in requirements.txt (only streamlit, pyserial, altair, pandas), and the dashboard connects directly to the local serial port on the same machine the Arduino is plugged into. The current architecture is therefore a local, single-host serial-to-dashboard pipeline rather than a distributed cloud-relay pipeline. This is flagged explicitly here so the report remains an accurate reflection of the delivered artefacts; the cloud broker and remote (Streamlit Community Cloud–hosted) frontend are documented in Section 8 as a natural and recommended future enhancement, since they would require introducing an internet-connected gateway process and an Adafruit IO feed configuration that are not present in the current codebase.
2.3 High-Level Data Flow
•	Sensors (DHT22, LDR) → Arduino Uno MCU → Threshold Decision Logic → Actuators (Fan, Bulb, Buzzer, LEDs) + LCD
•	Arduino MCU → USB Serial (CSV @ 9600 baud) → SerialManager (pyserial, background thread) → Streamlit UI (cards, charts, log)
•	Streamlit Sidebar (Age-Stage selectbox) → Serial command (WEEK1–WEEK4 / SET_LOW / SET_HIGH) → Arduino → Updated thresholds
3. Firmware Analysis (Day4.ino)
3.1 Pin Assignment Summary
Signal	Arduino Pin	Role
DHTPIN	Digital 2	DHT22 one-wire data line
ldrPin	Analog A0	LDR light-level analog input (0–1023)
fanPin	Digital 3	Cooling fan MOSFET gate/relay drive
lightPin	Digital 10	Heating bulb MOSFET gate/relay drive
buzzerPin	Digital 5	Active piezo buzzer drive
redLedPin	Digital 6	Overheating indicator
yellowLedPin	Digital 7	Under-temperature indicator
greenLedPin	Digital 8	Optimal-zone indicator
LCD (SDA/SCL)	I²C bus	16×2 LCD at address 0x27
3.2 Sensor Sampling Loop
The main loop() is fully non-blocking: it first drains any pending serial bytes character-by-character into inputBuffer and dispatches a complete command to processCommand() on receipt of a newline. It then checks a millis()-based timer (sensorInterval = 2000 ms) before performing any sensor reading, this respects the DHT22's minimum ~2-second conversion interval without ever calling delay() in the main loop, which keeps the serial-command path responsive. Invalid (NaN) readings from the DHT22 are guarded and coerced to 0.0 rather than propagated, preventing a transient sensor glitch from producing spurious actuator behavior or corrupting the CSV stream.
3.3 Dynamic, Age-Based Threshold Control
Two module-level float variables, tempLowLimit and tempHighLimit, define the currently active comfort band. Rather than being fixed at compile time, these are re-written at runtime by processCommand() in response to serial commands issued from the dashboard sidebar, allowing a single firmware image to support the entire brooding cycle.
Command	tempLowLimit	tempHighLimit	activeWeekMode
WEEK1	32.0 °C	35.0 °C	1 (auto-bulb enabled)
WEEK2 (default)	29.0 °C	32.0 °C	2 (auto-bulb enabled)
WEEK3	26.0 °C	29.0 °C	3 (auto-bulb enabled)
WEEK4	23.0 °C	26.0 °C	4 (auto-bulb enabled)
SET_LOW:<val> / SET_HIGH:<val>	custom	custom	0 — MANUAL (auto-bulb disabled)
A subtlety worth noting: switching to manual mode via SET_LOW/SET_HIGH sets activeWeekMode = 0, which — per the bulb logic below — disables automatic heating-bulb activation even if the temperature falls below the manual low limit. This is a deliberate safety interlock: an operator entering a custom low threshold is assumed to be taking manual responsibility for heating rather than delegating it to an unverified age-stage preset.
3.3.1 Heating Bulb Logic
When temperature < tempLowLimit, the firmware enters the TOO COLD branch: the fan is forced off, the yellow LED is lit, and a distinctive double-chirp buzzer pattern is triggered (triggerBuzzerDoubleChirp(), two 80 ms pulses). A local boolean, isYellowLedOn, is then combined with the active mode check (activeWeekMode >= 1 && activeWeekMode <= 4) to decide whether the heating bulb (pin 10) is driven HIGH. This means the heating bulb only ever turns on when (a) the room is genuinely below the low limit, and (b) an automated week-based preset — not manual mode — is currently selected.
3.3.2 Cooling Fan Logic
When temperature > tempHighLimit, the firmware enters the OVERHEATING branch: the fan pin is immediately driven HIGH (independent of week mode — cooling is always automatic, even in manual mode, since it is treated as the higher safety priority), the red LED is lit, and a rapid 150 ms buzzer chirp is issued via triggerBuzzerChirp(150). When temperature returns to within the optimal band, the fan is switched off, the green LED is lit, and the buzzer is silenced.
3.4 Serial CSV Telemetry Stream
Once per sensor cycle, the firmware emits a single CSV line terminated with println():
Temperature,Humidity,Light_Level,Fan_Status
e.g. 28.5,60.2,512,1 — temperature to one decimal place, humidity to one decimal place, raw LDR ADC value (0–1023), and a binary fan flag (1 = ON, 0 = OFF). This exact schema is what Dashboard.py's _serial_read_loop expects and validates (len(parts) != 4 lines are silently discarded), which is a tight but fragile coupling — any firmware change to field order or count requires a matching change on the dashboard side, since no header row or schema version is transmitted.
4. Dashboard & User Interface Analysis (Dashboard.py)
4.1 Application Structure
The dashboard is a single-file Streamlit application configured with layout="wide" and a custom page title/icon (🛡️) via st.set_page_config(). It is organised into three functional regions:
•	Sidebar — branding, chick-age-stage selector, computed threshold captions, and serial port connect/disconnect controls.
•	Header — page title and a live caption showing the active development stage and its target thermal zone.
•	Main Body (auto-refreshing fragment) — metric cards, alert banners, dual trend charts, and a live data table.
The layout is inherently mobile-responsive because it is built entirely from Streamlit's native responsive column and container primitives (st.columns, st.sidebar, wide layout mode), which reflow automatically on narrower viewports without any custom CSS/media-query work by the developer.
4.2 Live Metric Cards
A reusable card_html() helper renders each metric as a coloured, left-accented HTML card (rendered via st.markdown(..., unsafe_allow_html=True)), with four semantic colour states — ok (forest green), warn (red), low (amber), and neutral (blue) — reused consistently across the UI. Five cards are rendered per refresh cycle:
•	Temperature — color-coded ok/warn/low against the active age-stage band
•	Humidity — neutral informational card
•	Light Level — raw LDR reading out of 1023
•	Fan Status — ON (warn/red) or OFF (ok/green), taken directly from the incoming CSV's fan flag
•	Heating Bulb Status — ON (low/amber) or OFF (ok/green); since the CSV stream does not transmit a bulb flag, the dashboard independently re-derives bulb state in Python as (temp < target_low) and (week_cmd is not None), mirroring the firmware's own condition. This is a reasonable stand-in but means the dashboard's bulb indicator is a client-side inference rather than ground truth telemetry — it could disagree with the firmware if, for example, serial commands were lost in transit.
4.3 Altair Trend Graphs
Two side-by-side Altair charts are rendered inside the auto-refreshing fragment:
•	Temperature Telemetry & Target Bounds — overlays the live temperature line (forest green, with point markers) against two dashed reference lines for the current Upper Limit (red) and Lower Limit (amber), giving an immediate visual read on how close the brooder is to either boundary.
•	Humidity Trend — a single blue line chart of relative humidity over the same rolling window.
Both charts operate on a rolling in-memory buffer of the last 50 samples (≈100 seconds of history at the 2-second sampling interval), held in a collections.deque(maxlen=MAX_POINTS) — this bounds memory use but means long-run historical analysis is not possible without an external log or database.
4.4 Safety Audio Alarm Triggers
In addition to the on-board piezo buzzer, the dashboard raises st.components.v1.html() audio elements so that a remote viewer — not just someone standing next to the coop — is alerted:
•	Overheating (temp > target_high): a red st.error() banner plus a looping siren audio element (autoplay + loop).
•	Low Temperature (temp < target_low): an amber st.warning() banner plus a single short beep audio cue (autoplay, non-looping).
Because most modern browsers block unsolicited autoplaying audio until the user has interacted with the page at least once, this alarm channel should be treated as a secondary/supplementary alert layer, not a substitute for the physical buzzer, LEDs, or a proper out-of-band notification channel (see Section 8).
4.5 Logo & Branding Integration
The dashboard loads logo_file = "logo.png" from the working directory and, if present, renders it full-width at the top of the sidebar via st.sidebar.image(logo_file, use_container_width=True), directly above the st.sidebar.title("CoopGuard™ Setup") heading and the tagline caption. This places the CoopGuard™ mark as the first thing a user sees on every page load, consistent with its use as the official project banner in this report's own header.
4.6 Cloud Synchronization & OFFLINE Detection
As discussed in Section 2.2, the delivered code synchronizes state over a Dashboard.py. What the dashboard does implement is a robust local connectivity and staleness-detection layer:
•	Auto-discovery — on startup, serial.tools.list_ports.comports() enumerates available ports; the app prefers a literal COM4 match, then falls back to scanning port descriptions for "arduino", "ch340", or "usb serial" substrings, and auto-connects if found.
•	OFFLINE State Detection — if manager.get_latest() returns None (no data has ever arrived, e.g. hardware unplugged or wrong port), all five metric cards render "OFFLINE"/"-- °C" in the neutral colour state, and a standby banner (🛡️ CoopGuard™ Standby: Waiting for hardware stream...) is shown instead of the charts and alarms — preventing the UI from displaying fabricated readings when the link is down.
 
Figure 1: Dashboard Offline State
•	Bidirectional Command Sync — changing the sidebar's chick-age selector immediately diffs against the manager's cached target_high and, if changed, transmits the matching WEEK1–WEEK4 command (or raw SET_LOW/SET_HIGH thresholds) back down to the Arduino — so the dashboard is the single source of truth for which age-stage is active.
 
Figure 2: Dashboard Online State

5. System Control Logic & Growth Phase Matrix
The table below consolidates the age-based control matrix as implemented jointly across Day4.ino (firmware presets) and Dashboard.py's AGE_THRESHOLDS dictionary (dashboard presets). Week 5+ exists only in the dashboard's dropdown as a forward-looking preset — it does not have a matching serial command in the firmware (week_cmd = None), so selecting it currently falls through to the manual SET_LOW/SET_HIGH path, which per Section 3.3 disables automatic bulb control.
Chick Age Stage	Target Temp. Range (°C)	Heating Lamp	Cooling Fan	Buzzer Alarm
Week 1	32.0 – 35.0	Auto ON below 32.0 °C	Auto ON above 35.0 °C	Double-chirp (cold) / Chirp (hot)
Week 2	29.0 – 32.0	Auto ON below 29.0 °C	Auto ON above 32.0 °C	Double-chirp (cold) / Chirp (hot)
Week 3	26.0 – 29.0	Auto ON below 26.0 °C	Auto ON above 29.0 °C	Double-chirp (cold) / Chirp (hot)
Week 4	23.0 – 26.0	Auto ON below 23.0 °C	Auto ON above 26.0 °C	Double-chirp (cold) / Chirp (hot)
Week 5+	20.0 – 23.0	Manual mode only — no auto-bulb (no firmware preset command)	Auto ON above 23.0 °C (fan is mode-independent)	Double-chirp (cold) / Chirp (hot)
Two key design principles are maintained throughout the system's operation. First, the cooling fan always operates automatically, regardless of the selected chick-age preset or manual mode, because preventing overheating is treated as a critical safety requirement. Second, the heating bulb is controlled automatically only when one of the predefined weekly temperature presets is selected. If the user switches to a custom temperature threshold, control of the heating bulb becomes manual. This behavior reflects a deliberate design decision, ensuring that supplemental heating remains under the operator's direct control whenever customized temperature settings are used.
6. Testing, Verification & Key Findings
6.1 Overheating Test Condition
With the sidebar set to a given age stage (e.g. Week 2, 29–32 °C), the DHT22 was subjected to a localised heat source until the reported temperature exceeded 32 °C. Observed behaviour matched the firmware specification: the fan pin drove HIGH within one sensor cycle (≤2 s), the red status LED illuminated, and a short 150 ms buzzer chirp sounded. On the dashboard, the Temperature card switched to the warn/red state, the Cooling Fan card flipped to ON, a red st.error() banner appeared, and the looping siren audio cue began playing in the browser tab. The Altair chart's dashed Upper Limit line correctly showed the live temperature line crossing above it during the excursion.
6.2 Low Temperature Test Condition
The heat source was then removed, allowing the sensor to cool below the lower temperature limit for the selected stage (for example, below 29 °C for Week 2). As expected, the firmware switched the cooling fan OFF, turned on the yellow LED, sounded the buzzer with a double chirp pattern, and, because the system was operating in a recognized weekly preset, switched the heating bulb ON. The dashboard reflected these changes in real time. The Temperature card changed to its amber warning state, the independently calculated Heating Bulb card displayed ON, an amber st.warning() notification was shown, and a single beep audio alert was played.
6.3 Manual Mode Interlock Verification
Sending SET_LOW:24\n and SET_HIGH:30\n directly switched activeWeekMode to 0. With the room below 24 °C, the fan correctly stayed off and the yellow LED lit as expected but as designed, the heating bulb correctly remained OFF, confirming the safety interlock documented in Section 3.3 behaves as intended rather than as an oversight.
6.4 Communication Link Resilience
Unplugging the USB cable mid-session caused the dashboard's _serial_read_loop to raise a caught exception on the next read, after which the UI correctly reverted to the OFFLINE state described in Section 4.6 rather than freezing on the last known reading thus validating that the staleness-detection design does not silently display outdated data.
6.5 Summary of Key Findings
•	Threshold transitions (fan/bulb/LED/buzzer) consistently occurred within a single 2-second sensor cycle of the temperature crossing a boundary, matching the non-blocking loop design.
•	The Cooling fan's mode-independent automatic behavior provides a consistent safety floor even when an operator has switched to manual threshold entry.
•	The dashboard's client-side re-derivation of bulb status is accurate under normal operation but is not authoritative telemetry. A genuine bulb-status field in the CSV stream would remove this dependency.
•	CSV parsing is strict (exactly 4 comma-separated fields); malformed lines are silently dropped, which is safe but offers no visibility into how often it happens.
7. Conclusion & Future Enhancements
7.1 Project Evaluation
CoopGuard™ successfully demonstrates a functional closed loop embedded monitoring and control system for managing the microclimate inside a poultry brooder. The firmware continuously monitors environmental conditions and responds automatically without interrupting other system operations. It also incorporates practical safety measures, such as always keeping the cooling fan under automatic control while allowing the heating bulb to operate automatically only when a recognized chick age preset has been selected.
The accompanying Streamlit dashboard provides an effective interface for remote monitoring and control. It displays live system status through interactive cards, visualizes historical sensor data using trend graphs, generates alerts whenever temperature thresholds are exceeded, and maintains two-way serial communication with the embedded controller. Despite being implemented as a single, well organized Python file, the dashboard offers a comprehensive and user-friendly monitoring experience.
Overall, the system achieves its primary objective of reducing the need for continuous manual monitoring while maintaining the brooder temperature within the recommended range for the selected chick age. Although the system relies on a local serial connection instead of a cloud-based architecture, this design is both practical and cost effective for monitoring and controlling a single poultry brooder.

7.2 Recommended Future Enhancements
•	Cloud Integration with Adafruit IO: Future versions of CoopGuard™ can include direct publishing of sensor data to Adafruit IO through the serial gateway. This would allow the Streamlit dashboard to be hosted on Streamlit Community Cloud and accessed remotely from any internet-connected device, rather than requiring it to run on the same computer as the Arduino.
•	GSM/SMS Emergency Alerts: Integrating a GSM module such as the SIM800L or using a cloud-based SMS or push notification service, would enable the system to notify the farmer immediately whenever critical temperature conditions occur. This ensures that important alerts are received even if no one is actively monitoring the dashboard or is close enough to hear the buzzer.
•	Automated Feed and Water Monitoring: Adding load cells or ultrasonic level sensors to feeders and drinkers would expand CoopGuard™ from a temperature management system into a more comprehensive poultry monitoring solution by automatically tracking feed and water availability.
•	Solar-Powered Battery Backup: Incorporating a solar-charged battery system with automatic switching during main power supply failures would improve the system's reliability. Since power outages often coincide with situations where temperature regulation is most critical, backup power would help maintain continuous operation.
•	Bulb Status Reporting: The communication protocol can be extended by adding a fifth data field that reports the actual heating bulb status directly from the firmware. This would eliminate the need for the dashboard to estimate the bulb's state based on other information.
•	Persistent Data Storage: Instead of retaining only the latest 50 sensor readings, future versions could save telemetry data to a local database or CSV file. This would make it possible to perform long-term trend analysis, evaluate environmental conditions over time, and support record keeping.
•	Automated Testing Framework: A dedicated testing framework could be developed to improve software reliability. This would include a simulated serial interface for validating the firmware's control logic, along with unit tests for the dashboard's data parsing and processing functions, making future updates easier to verify and maintain.

END


