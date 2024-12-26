/*
 * MAIA ESP32-CAM Firmware
 * Handles audio streaming and camera feed for MAIA Home Assistant module
 */

#include "esp_camera.h"
#include <WiFi.h>
#include <WebSocketsClient.h>
#include <ArduinoJson.h>
#include <driver/i2s.h>
#include <esp_wifi.h>
#include <esp_bt.h>
#include <esp_timer.h>
#include <esp_task_wdt.h>
#include <esp_pm.h>
#include "config.h"
#include "face_detection.h"
#include "audio_processor.h"
#include "motion_detector.h"
#include "ha_websocket.h"
#include "audio_stream.h"
#include "websocket_client.h"

// Global objects
FaceDetection face_detector;
AudioStream audio_stream;
WebSocketClient ws_client;

void setup() {
    Serial.begin(115200);
    
    // Initialize camera
    camera_config_t camera_config = CAMERA_CONFIG_DEFAULT;
    esp_err_t err = esp_camera_init(&camera_config);
    if (err != ESP_OK) {
        Serial.printf("Camera init failed with error 0x%x\n", err);
        return;
    }
    
    // Configure face detection
    FaceDetectionConfig face_config;
    face_config.detect_landmarks = true;
    face_config.cache_ttl = 1000;        // 1 second cache TTL
    face_config.max_cache_size = 100;    // Cache up to 100 faces
    
    if (!face_detector.begin(face_config)) {
        Serial.println("Failed to initialize face detection");
        return;
    }
    
    // Initialize audio streaming
    if (!audio_stream.begin()) {
        Serial.println("Failed to initialize audio streaming");
        return;
    }
    
    // Connect to WiFi and WebSocket server
    if (!ws_client.begin()) {
        Serial.println("Failed to initialize WebSocket client");
        return;
    }
}

void loop() {
    // Handle WebSocket connection
    ws_client.loop();
    
    // Process camera feed
    camera_fb_t* fb = esp_camera_fb_get();
    if (fb) {
        FaceDetectionResult face_result;
        if (face_detector.detectFaces(fb, &face_result)) {
            // Send face detection results over WebSocket
            if (face_result.faces > 0) {
                String json = "{\"type\":\"face_detection\",\"faces\":" + String(face_result.faces);
                json += ",\"confidences\":[";
                for (int i = 0; i < face_result.faces; i++) {
                    if (i > 0) json += ",";
                    json += String(face_result.confidences[i], 2);
                }
                json += "],\"boxes\":[";
                for (int i = 0; i < face_result.faces; i++) {
                    if (i > 0) json += ",";
                    json += "{\"x\":" + String(face_result.boxes[i].box_p[0]);
                    json += ",\"y\":" + String(face_result.boxes[i].box_p[1]);
                    json += ",\"width\":" + String(face_result.boxes[i].box_p[2] - face_result.boxes[i].box_p[0]);
                    json += ",\"height\":" + String(face_result.boxes[i].box_p[3] - face_result.boxes[i].box_p[1]) + "}";
                }
                json += "]";
                
                if (face_result.has_landmarks) {
                    json += ",\"landmarks\":[";
                    for (int i = 0; i < face_result.faces; i++) {
                        if (i > 0) json += ",";
                        json += "[";
                        for (int j = 0; j < face_result.landmark_count; j++) {
                            if (j > 0) json += ",";
                            json += "{\"x\":" + String(face_result.landmarks[i][j].x);
                            json += ",\"y\":" + String(face_result.landmarks[i][j].y) + "}";
                        }
                        json += "]";
                    }
                    json += "]";
                }
                
                json += "}";
                ws_client.sendMessage(json);
                
                // Log cache performance periodically
                static uint32_t last_stats = 0;
                uint32_t now = millis();
                if (now - last_stats >= 5000) {  // Every 5 seconds
                    float hit_rate = face_detector.getCacheHitRate();
                    Serial.printf("Face detection cache hit rate: %.1f%%\n", hit_rate);
                    last_stats = now;
                }
            }
        }
        esp_camera_fb_return(fb);
    }
    
    // Process audio
    audio_stream.loop();
    
    // Small delay to prevent watchdog reset
    delay(10);
} 