#ifndef BASE_CONFIG_H
#define BASE_CONFIG_H

#include <Arduino.h>
#include <ArduinoJson.h>
#include <WiFi.h>
#include <PubSubClient.h>
#include <ESPmDNS.h>
#include <Wire.h>
#include <DHT.h>
#include <BLEDevice.h>
#include <BLEServer.h>
#include <BLEUtils.h>
#include <BLEUUID.h>

// Sensor type definitions
#define SENSOR_NONE      0x00
#define SENSOR_DHT22     0x01
#define SENSOR_BME280    0x02
#define SENSOR_MIC       0x04
#define SENSOR_PIR       0x08
#define SENSOR_LIGHT     0x10
#define SENSOR_CAMERA    0x20
#define SENSOR_BLE       0x40
#define SENSOR_WIFI_SCAN 0x80

// MQTT topics
#define MQTT_DISCOVERY_PREFIX "homeassistant"
#define MQTT_STATE_TOPIC "maia/sensor/%s/%s/state"
#define MQTT_CONFIG_TOPIC "maia/sensor/%s/%s/config"
#define MQTT_AVAILABILITY_TOPIC "maia/sensor/%s/status"

class BaseConfig {
protected:
    // Device info
    String device_id;
    String device_name;
    uint32_t sensor_mask;
    
    // Network
    String wifi_ssid;
    String wifi_password;
    String mqtt_server;
    int mqtt_port;
    String mqtt_user;
    String mqtt_password;
    
    // HA integration
    String ha_discovery_prefix;
    
    // Sensor data
    StaticJsonDocument<512> sensor_data;
    
public:
    BaseConfig() : sensor_mask(SENSOR_NONE), mqtt_port(1883) {
        device_id = String((uint32_t)ESP.getEfuseMac(), HEX);
        device_name = "MAIA_" + device_id;
    }
    
    virtual bool begin() {
        // Initialize WiFi
        WiFi.mode(WIFI_STA);
        WiFi.begin(wifi_ssid.c_str(), wifi_password.c_str());
        
        // Wait for connection
        int attempts = 0;
        while (WiFi.status() != WL_CONNECTED && attempts < 20) {
            delay(500);
            Serial.print(".");
            attempts++;
        }
        
        if (WiFi.status() != WL_CONNECTED) {
            Serial.println("WiFi connection failed");
            return false;
        }
        
        Serial.println("\nWiFi connected");
        Serial.println("IP address: " + WiFi.localIP().toString());
        
        // Start mDNS
        if (!MDNS.begin(device_name.c_str())) {
            Serial.println("Error starting mDNS");
            return false;
        }
        
        return true;
    }
    
    virtual void loop() {
        // Base loop functionality
    }
    
    bool parseConfig(const char* json_config) {
        StaticJsonDocument<1024> doc;
        DeserializationError error = deserializeJson(doc, json_config);
        
        if (error) {
            Serial.println("Failed to parse config");
            return false;
        }
        
        // Network config
        wifi_ssid = doc["wifi_ssid"].as<String>();
        wifi_password = doc["wifi_password"].as<String>();
        mqtt_server = doc["mqtt_server"].as<String>();
        mqtt_port = doc["mqtt_port"] | 1883;
        mqtt_user = doc["mqtt_user"].as<String>();
        mqtt_password = doc["mqtt_password"].as<String>();
        
        // Sensor config
        sensor_mask = 0;
        JsonArray sensors = doc["sensors"].as<JsonArray>();
        for (JsonVariant sensor : sensors) {
            const char* sensor_type = sensor["type"];
            if (strcmp(sensor_type, "dht22") == 0) sensor_mask |= SENSOR_DHT22;
            else if (strcmp(sensor_type, "bme280") == 0) sensor_mask |= SENSOR_BME280;
            else if (strcmp(sensor_type, "mic") == 0) sensor_mask |= SENSOR_MIC;
            else if (strcmp(sensor_type, "pir") == 0) sensor_mask |= SENSOR_PIR;
            else if (strcmp(sensor_type, "light") == 0) sensor_mask |= SENSOR_LIGHT;
            else if (strcmp(sensor_type, "camera") == 0) sensor_mask |= SENSOR_CAMERA;
            else if (strcmp(sensor_type, "ble") == 0) sensor_mask |= SENSOR_BLE;
            else if (strcmp(sensor_type, "wifi_scan") == 0) sensor_mask |= SENSOR_WIFI_SCAN;
        }
        
        return true;
    }
    
    virtual void publishDiscovery() {
        // Publish HA MQTT discovery configs for enabled sensors
    }
    
    virtual void publishState() {
        // Publish sensor states
    }
    
protected:
    String getMQTTTopic(const char* type, const char* sensor) {
        char topic[128];
        snprintf(topic, sizeof(topic), type, device_id.c_str(), sensor);
        return String(topic);
    }
    
    void publishHA(const char* component, const char* sensor, JsonDocument& config) {
        // Add device info
        JsonObject device = config.createNestedObject("device");
        device["identifiers"] = device_id;
        device["name"] = device_name;
        device["model"] = "MAIA Companion";
        device["manufacturer"] = "MAIA";
        
        // Add availability topic
        config["availability_topic"] = getMQTTTopic(MQTT_AVAILABILITY_TOPIC, "");
        
        // Publish discovery message
        String topic = ha_discovery_prefix + "/" + component + "/" + device_id + "/" + sensor + "/config";
        // TODO: Implement MQTT publish
    }
};

#endif // BASE_CONFIG_H 