#include "../base_config.h"
#include <WiFi.h>
#include <BLEScan.h>
#include <BLEAdvertisedDevice.h>
#include <PubSubClient.h>

class ScannerConfig : public BaseConfig {
private:
    WiFiClient wifi_client;
    PubSubClient mqtt_client;
    BLEScan* ble_scan;
    unsigned long last_scan_time;
    int scan_interval;  // configurable interval in seconds
    
    // Scan results
    StaticJsonDocument<4096> ble_devices;
    StaticJsonDocument<4096> wifi_networks;
    
public:
    ScannerConfig() : mqtt_client(wifi_client), last_scan_time(0), scan_interval(30) {}
    
    bool begin() override {
        if (!BaseConfig::begin()) {
            return false;
        }
        
        // Initialize MQTT
        mqtt_client.setServer(mqtt_server.c_str(), mqtt_port);
        mqtt_client.setCallback([this](char* topic, byte* payload, unsigned int length) {
            this->handleMQTTMessage(topic, payload, length);
        });
        
        if (!connectMQTT()) {
            Serial.println("MQTT connection failed");
            return false;
        }
        
        // Initialize BLE if enabled
        if (sensor_mask & SENSOR_BLE) {
            BLEDevice::init(device_name.c_str());
            ble_scan = BLEDevice::getScan();
            ble_scan->setActiveScan(true);
            ble_scan->setInterval(100);
            ble_scan->setWindow(99);
        }
        
        // Subscribe to config topic
        mqtt_client.subscribe(getMQTTTopic(MQTT_CONFIG_TOPIC, "").c_str());
        
        // Publish discovery configs
        publishDiscovery();
        
        return true;
    }
    
    void loop() override {
        if (!mqtt_client.connected()) {
            connectMQTT();
        }
        mqtt_client.loop();
        
        unsigned long now = millis();
        if (now - last_scan_time > (scan_interval * 1000)) {
            performScans();
            last_scan_time = now;
        }
    }
    
private:
    bool connectMQTT() {
        if (!mqtt_client.connected()) {
            String client_id = "MAIA_Scanner_" + device_id;
            
            if (mqtt_client.connect(client_id.c_str(), mqtt_user.c_str(), mqtt_password.c_str())) {
                mqtt_client.publish(getMQTTTopic(MQTT_AVAILABILITY_TOPIC, "").c_str(), "online", true);
                mqtt_client.subscribe(getMQTTTopic(MQTT_CONFIG_TOPIC, "").c_str());
            }
        }
        return mqtt_client.connected();
    }
    
    void handleMQTTMessage(char* topic, byte* payload, unsigned int length) {
        StaticJsonDocument<512> doc;
        DeserializationError error = deserializeJson(doc, payload, length);
        
        if (error) {
            Serial.println("Failed to parse config message");
            return;
        }
        
        if (doc.containsKey("scan_interval")) {
            scan_interval = doc["scan_interval"].as<int>();
        }
    }
    
    void performScans() {
        if (sensor_mask & SENSOR_BLE) {
            performBLEScan();
        }
        
        if (sensor_mask & SENSOR_WIFI_SCAN) {
            performWiFiScan();
        }
    }
    
    void performBLEScan() {
        ble_devices.clear();
        JsonArray devices = ble_devices.createNestedArray("devices");
        
        BLEScanResults scan_results = ble_scan->start(5, false);
        for(int i = 0; i < scan_results.getCount(); i++) {
            BLEAdvertisedDevice device = scan_results.getDevice(i);
            JsonObject dev = devices.createNestedObject();
            
            dev["address"] = device.getAddress().toString();
            dev["rssi"] = device.getRSSI();
            
            if (device.haveName()) {
                dev["name"] = device.getName();
            }
            
            if (device.haveManufacturerData()) {
                String manufData = "";
                std::string strManufData = device.getManufacturerData();
                for (int i = 0; i < strManufData.length(); i++) {
                    char str[3];
                    sprintf(str, "%02X", (uint8_t)strManufData[i]);
                    manufData += str;
                }
                dev["manufacturer_data"] = manufData;
            }
        }
        
        // Publish BLE scan results
        String output;
        serializeJson(ble_devices, output);
        mqtt_client.publish(getMQTTTopic(MQTT_STATE_TOPIC, "ble").c_str(), output.c_str(), true);
    }
    
    void performWiFiScan() {
        wifi_networks.clear();
        JsonArray networks = wifi_networks.createNestedArray("networks");
        
        int n = WiFi.scanNetworks();
        for (int i = 0; i < n; ++i) {
            JsonObject network = networks.createNestedObject();
            network["ssid"] = WiFi.SSID(i);
            network["rssi"] = WiFi.RSSI(i);
            network["bssid"] = WiFi.BSSIDstr(i);
            network["channel"] = WiFi.channel(i);
            network["encryption"] = WiFi.encryptionType(i);
        }
        
        // Publish WiFi scan results
        String output;
        serializeJson(wifi_networks, output);
        mqtt_client.publish(getMQTTTopic(MQTT_STATE_TOPIC, "wifi").c_str(), output.c_str(), true);
    }
};

ScannerConfig scanner;

void setup() {
    Serial.begin(115200);
    Serial.println("MAIA Scanner");
    
    // Wait for configuration
    while (!scanner.parseConfig(Serial.readStringUntil('\n').c_str())) {
        delay(1000);
    }
    
    if (!scanner.begin()) {
        Serial.println("Failed to initialize scanner");
        return;
    }
    
    Serial.println("Scanner initialized");
}

void loop() {
    scanner.loop();
} 