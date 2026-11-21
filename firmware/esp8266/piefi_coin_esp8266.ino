// PieFi OS Lite V3 - ESP8266 backup coin controller
// Arduino IDE library: ArduinoJson 7.x. Use an optocoupler/open-collector interface.
#include <ESP8266WiFi.h>
#include <ESP8266HTTPClient.h>
#include <WiFiClient.h>
#include <ArduinoJson.h>
extern "C" {
#include "user_interface.h"
}
const char* WIFI_SSID="YOUR_PIEFI_LAN_WIFI";
const char* WIFI_PASSWORD="YOUR_WIFI_PASSWORD";
const char* API_BASE="http://10.0.0.1";
const char* API_TOKEN="PASTE_CONTROLLER_TOKEN_FROM_PIEFI_ADMIN";
const char* DEVICE_ID="esp8266-backup";
const int COIN_PIN=D5; // GPIO14, isolated pulse input only; never raw 12V
const uint32_t QUIET_US=250000;
volatile uint32_t pulseCount=0,lastPulseUs=0;
String activeSession="";uint32_t lastPoll=0,eventCounter=0,bootNonce=0;
void ICACHE_RAM_ATTR onCoinPulse(){pulseCount++;lastPulseUs=micros();}
String eventId(){return String(bootNonce,HEX)+"-"+String(millis())+"-"+String(++eventCounter);}
void heartbeat(){WiFiClient c;HTTPClient h;h.begin(c,String(API_BASE)+"/api/controller/heartbeat");h.addHeader("Authorization",String("Bearer ")+API_TOKEN);h.addHeader("Content-Type","application/json");h.POST("{\"device_id\":\"esp8266-backup\",\"firmware\":\"piefi-esp8266-v1\"}");h.end();}
void pollSession(){WiFiClient c;HTTPClient h;h.begin(c,String(API_BASE)+"/api/controller/next-session?device_id=esp8266-backup&firmware=piefi-esp8266-v1");h.addHeader("Authorization",String("Bearer ")+API_TOKEN);int code=h.GET();if(code==200){JsonDocument d;if(!deserializeJson(d,h.getString())){if(d["active"]==true&&!d["session"].isNull())activeSession=String((const char*)d["session"]["id"]);else activeSession="";}}h.end();}
void sendCoin(uint32_t pulses){if(activeSession.length()==0||!pulses)return;String eid=eventId();JsonDocument d;d["device_id"]=DEVICE_ID;d["session_id"]=activeSession;d["event_id"]=eid;d["pulses"]=pulses;d["firmware"]="piefi-esp8266-v1";String body;serializeJson(d,body);for(int attempt=0;attempt<3;attempt++){WiFiClient c;HTTPClient h;h.begin(c,String(API_BASE)+"/api/controller/coin");h.addHeader("Authorization",String("Bearer ")+API_TOKEN);h.addHeader("Content-Type","application/json");int code=h.POST(body);String reply=h.getString();h.end();if(code==200||(code==409&&reply.indexOf("duplicate_event")>=0))return;delay(300);}}
void setup(){bootNonce=os_random();Serial.begin(115200);pinMode(COIN_PIN,INPUT_PULLUP);attachInterrupt(digitalPinToInterrupt(COIN_PIN),onCoinPulse,FALLING);WiFi.mode(WIFI_STA);WiFi.begin(WIFI_SSID,WIFI_PASSWORD);while(WiFi.status()!=WL_CONNECTED)delay(500);heartbeat();}
void loop(){if(WiFi.status()!=WL_CONNECTED){WiFi.reconnect();delay(1000);return;}if(millis()-lastPoll>=1000){lastPoll=millis();heartbeat();pollSession();}uint32_t n=0,last=0;noInterrupts();n=pulseCount;last=lastPulseUs;interrupts();if(n&&(uint32_t)(micros()-last)>QUIET_US){noInterrupts();n=pulseCount;pulseCount=0;interrupts();sendCoin(n);}delay(5);}
