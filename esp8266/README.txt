PieFi ESP8266 coin-node prototype
- Configure Wi-Fi and server URL/token before deploying.
- Server route: POST /api/node/coin with JSON {device: MAC, credits:1,event_key:unique}.
- Authentication: Bearer token from /etc/piefi/node-token (copy securely from device).
- Duplicate event keys are rejected by SQLite.
- Do not expose this endpoint directly to the internet; use LAN only.
- Coin acceptor pulse wiring requires proper voltage isolation/conditioning; never connect high voltage directly to GPIO.
