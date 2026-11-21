// PieFi ESP8266 Coin Node — prototype firmware. Configure Wi-Fi/API credentials before flashing.
#include <ESP8266WiFi.h>
#include <ESP8266HTTPClient.h>
#include <WiFiClient.h>
#include <ArduinoJson.h>
const char* WIFI_SSID="PIEFI_NODE_WIFI";
const char* WIFI_PASS="CHANGE_ME";
const char* API_URL="http://10.0.0.1:8080/api/coin";
const char* API_TOKEN="CHANGE_ME_ADMIN_TOKEN";
const char* DEVICE_MAC="00:00:00:00:00:00"; // set paired customer device MAC in node config for real deployments
const int COIN_PIN=D5;
volatile uint32_t pulses=0;
volatile uint32_t lastPulseMs=0;
void IRAM_ATTR coinPulse(){uint32_t now=millis();if(now-lastPulseMs>80){pulses++;lastPulseMs=now;}}
void setup(){Serial.begin(115200);pinMode(COIN_PIN,INPUT_PULLUP);attachInterrupt(digitalPinToInterrupt(COIN_PIN),coinPulse,FALLING);WiFi.mode(WIFI_STA);WiFi.begin(WIFI_SSID,WIFI_PASS);}
void loop(){static uint32_t lastSend=0;uint32_t count=0;noInterrupts();if(pulses&&millis()-lastPulseMs>350){count=pulses;pulses=0;}interrupts();if(count){if(WiFi.status()==WL_CONNECTED){WiFiClient client;HTTPClient http;http.begin(client,API_URL);http.addHeader("Content-Type","application/json");http.addHeader("Authorization",String("Bearer ")+API_TOKEN);String eventKey=String("node-")+WiFi.macAddress()+"-"+String(millis());String body=String("{\"device\":\"")+DEVICE_MAC+"\",\"credits\":"+count+",\"event_key\":\""+eventKey+"\"}";int code=http.POST(body);Serial.printf("coin event HTTP %d\n",code);http.end();}else Serial.println("coin event held only in volatile memory; network unavailable");}delay(20);}
