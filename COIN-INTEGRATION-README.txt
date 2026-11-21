PieFi OS Lite V3 - ESP32 Primary / ESP8266 Backup Coin Integration

ARCHITECTURE
- Customer opens the OpenNDS FAS page and selects an operator-configured package.
- PieFi creates one 5-minute pending coin session bound to the customer client IP, MAC and OpenNDS HID.
- ESP32 primary polls for the active session. ESP8266 backup is standby and may take over only when ESP32 heartbeat is older than 20 seconds.
- Coin acceptor emits one pulse train per coin. Controller sends a unique event ID and pulse count.
- PieFi maps that pulse count to a configured denomination, records the event idempotently, updates the payment total and creates a one-use OpenNDS authorization reservation after the selected package is paid.
- OpenNDS BinAuth validates the reservation against the original client IP/MAC and applies configured minutes and rates.
- Collection totals count only sessions acknowledged by OpenNDS as authorized. OpenNDS client tokens correlate the exact session through deauthentication.
- Firmware retries a coin event with the same event ID; the server rejects duplicates to prevent double-credit.

ADMIN SETUP
1. Open http://10.0.0.1/admin/coin.
2. Add coin packages (price, minutes, download/upload Mbps). No assumed price/time rates are enabled.
3. Measure each real coin acceptor denomination. Add exact pulse count -> peso mapping. Do not guess pulse counts.
4. Copy the Controller API token from the protected admin page into both firmware sketches.
5. Set Wi-Fi SSID/password in both sketches and upload ESP32 primary / ESP8266 backup firmware.
6. Confirm both controllers appear in dashboard. Test one coin denomination and verify the customer session is authorized.

HARDWARE SAFETY
- Coin acceptor output is commonly 12V. NEVER connect its signal directly to ESP32/ESP8266 GPIO.
- Use an optocoupler or properly designed transistor/level-shifting interface. For dual-controller backup, use electrically isolated outputs for each GPIO input.
- ESP32 input: GPIO27. ESP8266 input: D5 / GPIO14. Both use INPUT_PULLUP and falling-edge pulse counting.
- Verify pulse width, pulse spacing, ground isolation, and denomination pulse counts with a meter/oscilloscope before enabling live payments.
- This firmware does not assume the coin acceptor inhibit polarity. Verify the exact model and wire its inhibit/enable input through a safe driver so it cannot accept coins when no payment session is active; until then, physically disable the coin slot between sessions.
- The controller token is sent over local HTTP. Keep controller boards on the trusted LAN, block controller API access from WAN, and never port-forward these endpoints.
- The backup controller is logical standby. A physical dual-controller installation must fan out the acceptor signal through isolation; do not tie GPIO pins together.

LIMITATIONS / VALIDATION
- Firmware sketches require ArduinoJson 7.x and user Wi-Fi credentials / controller token.
- Not yet tested on Dell Wyse 5070, actual coin acceptor, ESP boards, or OpenNDS runtime.
- The BinAuth wrapper delegates the stock OpenNDS logging script and then applies PieFi policy; verify auth restore and event argument behavior against the exact OpenNDS package version shipped by ImageBuilder.
- Coin pulse map and packages must be configured before coin payments are enabled.
- One customer coin session at a time because one physical coin acceptor cannot safely distinguish simultaneous customer sessions.
- Coin overpayment is converted proportionally to extra minutes at the selected package rate; no change is dispensed.
