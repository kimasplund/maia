#include <WiFi.h>
#include <PubSubClient.h>
#include <BLEDevice.h>
#include <BLEUtils.h>
#include <BLEScan.h>
#include <BLEAdvertisedDevice.h>
#include <ArduinoJson.h>
#include <EEPROM.h>
#include <esp_wifi.h>

// Configuration
const char* WIFI_SSID = "";  // Set via config
const char* WIFI_PASSWORD = "";  // Set via config
const char* MQTT_SERVER = "";  // Set via config
const int MQTT_PORT = 1883;
const char* MQTT_USER = "";  // Set via config
const char* MQTT_PASSWORD = "";  // Set via config

// Device ID (last 6 characters of MAC address)
String DEVICE_ID = "";

// MQTT topics
String MQTT_TOPIC_DATA = "";      // ble_scanner/{device_id}/data
String MQTT_TOPIC_STATUS = "";    // ble_scanner/{device_id}/status
String MQTT_TOPIC_CONFIG = "";    // ble_scanner/{device_id}/config

// BLE scan parameters
int SCAN_TIME = 5;  // seconds
int SCAN_INTERVAL = 100;  // milliseconds
int SCAN_WINDOW = 99;    // milliseconds

// WiFi client
WiFiClient espClient;
PubSubClient mqttClient(espClient);

// BLE scanner
BLEScan* pBLEScan;

// Configuration storage
struct Config {
  char wifi_ssid[32];
  char wifi_password[64];
  char mqtt_server[64];
  char mqtt_user[32];
  char mqtt_password[32];
  float location_x;
  float location_y;
  float location_z;
  int scan_time;
  int scan_interval;
  int scan_window;
} config;

// Uptime tracking
unsigned long startTime;

class MyAdvertisedDeviceCallbacks: public BLEAdvertisedDeviceCallbacks {
    void onResult(BLEAdvertisedDevice advertisedDevice) {
      // Create JSON document
      StaticJsonDocument<512> doc;
      
      // Add device info
      doc["device_mac"] = advertisedDevice.getAddress().toString();
      doc["rssi"] = advertisedDevice.getRSSI();
      
      if(advertisedDevice.haveName()) {
        doc["device_name"] = advertisedDevice.getName();
      }
      
      // Add metadata
      JsonObject metadata = doc.createNestedObject("metadata");
      metadata["tx_power"] = advertisedDevice.getTXPower();
      metadata["address_type"] = advertisedDevice.getAddressType();
      
      if(advertisedDevice.haveServiceUUID()) {
        metadata["service_uuid"] = advertisedDevice.getServiceUUID().toString();
      }
      
      if(advertisedDevice.haveManufacturerData()) {
        std::string manufacturerData = advertisedDevice.getManufacturerData();
        char hex_str[manufacturerData.length() * 2 + 1];
        for (int i = 0; i < manufacturerData.length(); i++) {
          sprintf(&hex_str[i * 2], "%02x", (unsigned char)manufacturerData[i]);
        }
        metadata["manufacturer_data"] = hex_str;
      }
      
      // Serialize to string
      String output;
      serializeJson(doc, output);
      
      // Publish to MQTT
      mqttClient.publish(MQTT_TOPIC_DATA.c_str(), output.c_str());
    }
};

void setup() {
  // Initialize serial
  Serial.begin(115200);
  
  // Initialize EEPROM
  EEPROM.begin(sizeof(Config));
  
  // Load config
  loadConfig();
  
  // Set device ID
  uint8_t mac[6];
  esp_wifi_get_mac(WIFI_IF_STA, mac);
  char mac_str[13];
  sprintf(mac_str, "%02X%02X%02X%02X%02X%02X", mac[0], mac[1], mac[2], mac[3], mac[4], mac[5]);
  DEVICE_ID = String(mac_str).substring(6);
  
  // Set MQTT topics
  MQTT_TOPIC_DATA = "ble_scanner/" + DEVICE_ID + "/data";
  MQTT_TOPIC_STATUS = "ble_scanner/" + DEVICE_ID + "/status";
  MQTT_TOPIC_CONFIG = "ble_scanner/" + DEVICE_ID + "/config";
  
  // Initialize WiFi
  setupWiFi();
  
  // Initialize MQTT
  setupMQTT();
  
  // Initialize BLE
  setupBLE();
  
  // Record start time
  startTime = millis();
}

void loop() {
  // Ensure WiFi is connected
  if (WiFi.status() != WL_CONNECTED) {
    setupWiFi();
  }
  
  // Ensure MQTT is connected
  if (!mqttClient.connected()) {
    setupMQTT();
  }
  
  // Handle MQTT messages
  mqttClient.loop();
  
  // Perform BLE scan
  BLEScanResults foundDevices = pBLEScan->start(SCAN_TIME, false);
  pBLEScan->clearResults();
  
  // Publish status
  publishStatus();
  
  // Small delay
  delay(100);
}

void setupWiFi() {
  Serial.println("Connecting to WiFi...");
  
  WiFi.mode(WIFI_STA);
  WiFi.begin(config.wifi_ssid, config.wifi_password);
  
  int attempts = 0;
  while (WiFi.status() != WL_CONNECTED && attempts < 20) {
    delay(500);
    Serial.print(".");
    attempts++;
  }
  
  if (WiFi.status() == WL_CONNECTED) {
    Serial.println("\nWiFi connected");
    Serial.println("IP address: " + WiFi.localIP().toString());
  } else {
    Serial.println("\nWiFi connection failed");
  }
}

void setupMQTT() {
  Serial.println("Connecting to MQTT...");
  
  mqttClient.setServer(config.mqtt_server, MQTT_PORT);
  mqttClient.setCallback(mqttCallback);
  
  String clientId = "ESP32_" + DEVICE_ID;
  
  while (!mqttClient.connected()) {
    if (mqttClient.connect(clientId.c_str(), config.mqtt_user, config.mqtt_password)) {
      Serial.println("MQTT connected");
      
      // Subscribe to config topic
      mqttClient.subscribe(MQTT_TOPIC_CONFIG.c_str());
      
      // Publish initial status
      publishStatus();
    } else {
      Serial.print("MQTT connection failed, rc=");
      Serial.println(mqttClient.state());
      delay(5000);
    }
  }
}

void setupBLE() {
  Serial.println("Initializing BLE...");
  
  BLEDevice::init("");
  pBLEScan = BLEDevice::getScan();
  pBLEScan->setAdvertisedDeviceCallbacks(new MyAdvertisedDeviceCallbacks());
  pBLEScan->setActiveScan(true);
  pBLEScan->setInterval(SCAN_INTERVAL);
  pBLEScan->setWindow(SCAN_WINDOW);
}

void mqttCallback(char* topic, byte* payload, unsigned int length) {
  // Handle config updates
  if (String(topic) == MQTT_TOPIC_CONFIG) {
    // Parse JSON config
    StaticJsonDocument<512> doc;
    DeserializationError error = deserializeJson(doc, payload, length);
    
    if (error) {
      Serial.println("Failed to parse config");
      return;
    }
    
    // Update config
    if (doc.containsKey("wifi_ssid")) {
      strlcpy(config.wifi_ssid, doc["wifi_ssid"], sizeof(config.wifi_ssid));
    }
    if (doc.containsKey("wifi_password")) {
      strlcpy(config.wifi_password, doc["wifi_password"], sizeof(config.wifi_password));
    }
    if (doc.containsKey("mqtt_server")) {
      strlcpy(config.mqtt_server, doc["mqtt_server"], sizeof(config.mqtt_server));
    }
    if (doc.containsKey("mqtt_user")) {
      strlcpy(config.mqtt_user, doc["mqtt_user"], sizeof(config.mqtt_user));
    }
    if (doc.containsKey("mqtt_password")) {
      strlcpy(config.mqtt_password, doc["mqtt_password"], sizeof(config.mqtt_password));
    }
    if (doc.containsKey("location")) {
      config.location_x = doc["location"]["x"];
      config.location_y = doc["location"]["y"];
      config.location_z = doc["location"]["z"];
    }
    if (doc.containsKey("scan_time")) {
      config.scan_time = doc["scan_time"];
      SCAN_TIME = config.scan_time;
    }
    if (doc.containsKey("scan_interval")) {
      config.scan_interval = doc["scan_interval"];
      SCAN_INTERVAL = config.scan_interval;
      pBLEScan->setInterval(SCAN_INTERVAL);
    }
    if (doc.containsKey("scan_window")) {
      config.scan_window = doc["scan_window"];
      SCAN_WINDOW = config.scan_window;
      pBLEScan->setWindow(SCAN_WINDOW);
    }
    
    // Save config
    saveConfig();
    
    // Restart if WiFi or MQTT settings changed
    if (doc.containsKey("wifi_ssid") || doc.containsKey("wifi_password") ||
        doc.containsKey("mqtt_server") || doc.containsKey("mqtt_user") ||
        doc.containsKey("mqtt_password")) {
      ESP.restart();
    }
  }
}

void publishStatus() {
  StaticJsonDocument<256> doc;
  
  doc["status"] = "running";
  doc["uptime"] = (millis() - startTime) / 1000;
  doc["version"] = "1.0.0";
  doc["wifi_rssi"] = WiFi.RSSI();
  
  JsonObject location = doc.createNestedObject("location");
  location["x"] = config.location_x;
  location["y"] = config.location_y;
  location["z"] = config.location_z;
  
  String output;
  serializeJson(doc, output);
  
  mqttClient.publish(MQTT_TOPIC_STATUS.c_str(), output.c_str());
}

void loadConfig() {
  EEPROM.get(0, config);
  
  // Set defaults if not configured
  if (String(config.wifi_ssid).length() == 0) {
    strlcpy(config.wifi_ssid, WIFI_SSID, sizeof(config.wifi_ssid));
    strlcpy(config.wifi_password, WIFI_PASSWORD, sizeof(config.wifi_password));
    strlcpy(config.mqtt_server, MQTT_SERVER, sizeof(config.mqtt_server));
    strlcpy(config.mqtt_user, MQTT_USER, sizeof(config.mqtt_user));
    strlcpy(config.mqtt_password, MQTT_PASSWORD, sizeof(config.mqtt_password));
    config.location_x = 0.0;
    config.location_y = 0.0;
    config.location_z = 0.0;
    config.scan_time = SCAN_TIME;
    config.scan_interval = SCAN_INTERVAL;
    config.scan_window = SCAN_WINDOW;
    saveConfig();
  }
}

void saveConfig() {
  EEPROM.put(0, config);
  EEPROM.commit();
} 