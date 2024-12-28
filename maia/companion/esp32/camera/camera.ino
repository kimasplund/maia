#include "../base_config.h"
#include "esp_camera.h"
#include "esp_http_server.h"
#include <PubSubClient.h>

// Camera pins for AI Thinker ESP32-CAM
#define PWDN_GPIO_NUM     32
#define RESET_GPIO_NUM    -1
#define XCLK_GPIO_NUM      0
#define SIOD_GPIO_NUM     26
#define SIOC_GPIO_NUM     27
#define Y9_GPIO_NUM       35
#define Y8_GPIO_NUM       34
#define Y7_GPIO_NUM       39
#define Y6_GPIO_NUM       36
#define Y5_GPIO_NUM       21
#define Y4_GPIO_NUM       19
#define Y3_GPIO_NUM       18
#define Y2_GPIO_NUM        5
#define VSYNC_GPIO_NUM    25
#define HREF_GPIO_NUM     23
#define PCLK_GPIO_NUM     22

class CameraConfig : public BaseConfig {
private:
    WiFiClient wifi_client;
    PubSubClient mqtt_client;
    httpd_handle_t stream_httpd = NULL;
    camera_fb_t *fb = NULL;
    unsigned long last_capture_time;
    int capture_interval;  // configurable interval in seconds
    bool streaming_enabled;
    
public:
    CameraConfig() : mqtt_client(wifi_client), last_capture_time(0), capture_interval(1), streaming_enabled(true) {}
    
    bool begin() override {
        if (!BaseConfig::begin()) {
            return false;
        }
        
        // Initialize camera
        camera_config_t config;
        config.ledc_channel = LEDC_CHANNEL_0;
        config.ledc_timer = LEDC_TIMER_0;
        config.pin_d0 = Y2_GPIO_NUM;
        config.pin_d1 = Y3_GPIO_NUM;
        config.pin_d2 = Y4_GPIO_NUM;
        config.pin_d3 = Y5_GPIO_NUM;
        config.pin_d4 = Y6_GPIO_NUM;
        config.pin_d5 = Y7_GPIO_NUM;
        config.pin_d6 = Y8_GPIO_NUM;
        config.pin_d7 = Y9_GPIO_NUM;
        config.pin_xclk = XCLK_GPIO_NUM;
        config.pin_pclk = PCLK_GPIO_NUM;
        config.pin_vsync = VSYNC_GPIO_NUM;
        config.pin_href = HREF_GPIO_NUM;
        config.pin_sscb_sda = SIOD_GPIO_NUM;
        config.pin_sscb_scl = SIOC_GPIO_NUM;
        config.pin_pwdn = PWDN_GPIO_NUM;
        config.pin_reset = RESET_GPIO_NUM;
        config.xclk_freq_hz = 20000000;
        config.pixel_format = PIXFORMAT_JPEG;
        
        // Initialize with high specs to pre-allocate larger buffers
        if (psramFound()) {
            config.frame_size = FRAMESIZE_UXGA;
            config.jpeg_quality = 10;
            config.fb_count = 2;
        } else {
            config.frame_size = FRAMESIZE_SVGA;
            config.jpeg_quality = 12;
            config.fb_count = 1;
        }
        
        // Initialize camera
        esp_err_t err = esp_camera_init(&config);
        if (err != ESP_OK) {
            Serial.printf("Camera init failed with error 0x%x", err);
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
        
        // Subscribe to config topic
        mqtt_client.subscribe(getMQTTTopic(MQTT_CONFIG_TOPIC, "").c_str());
        
        // Start HTTP stream server
        startStreamServer();
        
        return true;
    }
    
    void loop() override {
        if (!mqtt_client.connected()) {
            connectMQTT();
        }
        mqtt_client.loop();
        
        unsigned long now = millis();
        if (now - last_capture_time > (capture_interval * 1000)) {
            captureAndPublish();
            last_capture_time = now;
        }
    }
    
private:
    bool connectMQTT() {
        if (!mqtt_client.connected()) {
            String client_id = "MAIA_Camera_" + device_id;
            
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
        
        if (doc.containsKey("capture_interval")) {
            capture_interval = doc["capture_interval"].as<int>();
        }
        if (doc.containsKey("streaming_enabled")) {
            streaming_enabled = doc["streaming_enabled"].as<bool>();
        }
    }
    
    void captureAndPublish() {
        if (!streaming_enabled) {
            return;
        }
        
        fb = esp_camera_fb_get();
        if (!fb) {
            Serial.println("Camera capture failed");
            return;
        }
        
        // Publish camera state
        StaticJsonDocument<256> state;
        state["streaming"] = streaming_enabled;
        state["resolution"] = String(fb->width) + "x" + String(fb->height);
        state["size"] = fb->len;
        
        String state_str;
        serializeJson(state, state_str);
        mqtt_client.publish(getMQTTTopic(MQTT_STATE_TOPIC, "camera").c_str(), state_str.c_str(), true);
        
        esp_camera_fb_return(fb);
    }
    
    static esp_err_t stream_handler(httpd_req_t *req) {
        camera_fb_t * fb = NULL;
        esp_err_t res = ESP_OK;
        size_t _jpg_buf_len = 0;
        uint8_t * _jpg_buf = NULL;
        char * part_buf[64];
        
        static const char* _STREAM_CONTENT_TYPE = "multipart/x-mixed-replace;boundary=123456789000000000000987654321";
        static const char* _STREAM_BOUNDARY = "\r\n--123456789000000000000987654321\r\n";
        static const char* _STREAM_PART = "Content-Type: image/jpeg\r\nContent-Length: %u\r\n\r\n";
        
        res = httpd_resp_set_type(req, _STREAM_CONTENT_TYPE);
        if (res != ESP_OK) {
            return res;
        }
        
        while (true) {
            fb = esp_camera_fb_get();
            if (!fb) {
                Serial.println("Camera capture failed");
                res = ESP_FAIL;
            } else {
                if (fb->format != PIXFORMAT_JPEG) {
                    bool jpeg_converted = frame2jpg(fb, 80, &_jpg_buf, &_jpg_buf_len);
                    esp_camera_fb_return(fb);
                    fb = NULL;
                    if (!jpeg_converted) {
                        Serial.println("JPEG compression failed");
                        res = ESP_FAIL;
                    }
                } else {
                    _jpg_buf_len = fb->len;
                    _jpg_buf = fb->buf;
                }
            }
            
            if (res == ESP_OK) {
                size_t hlen = snprintf((char *)part_buf, 64, _STREAM_PART, _jpg_buf_len);
                res = httpd_resp_send_chunk(req, _STREAM_BOUNDARY, strlen(_STREAM_BOUNDARY));
                if (res == ESP_OK) {
                    res = httpd_resp_send_chunk(req, (const char *)part_buf, hlen);
                    if (res == ESP_OK) {
                        res = httpd_resp_send_chunk(req, (const char *)_jpg_buf, _jpg_buf_len);
                    }
                }
            }
            
            if (fb) {
                esp_camera_fb_return(fb);
                fb = NULL;
                _jpg_buf = NULL;
            } else if (_jpg_buf) {
                free(_jpg_buf);
                _jpg_buf = NULL;
            }
            
            if (res != ESP_OK) {
                break;
            }
        }
        
        return res;
    }
    
    void startStreamServer() {
        httpd_config_t config = HTTPD_DEFAULT_CONFIG();
        config.server_port = 80;
        
        httpd_uri_t stream_uri = {
            .uri       = "/stream",
            .method    = HTTP_GET,
            .handler   = stream_handler,
            .user_ctx  = NULL
        };
        
        if (httpd_start(&stream_httpd, &config) == ESP_OK) {
            httpd_register_uri_handler(stream_httpd, &stream_uri);
        }
    }
};

CameraConfig camera;

void setup() {
    Serial.begin(115200);
    Serial.println("MAIA Camera");
    
    // Wait for configuration
    while (!camera.parseConfig(Serial.readStringUntil('\n').c_str())) {
        delay(1000);
    }
    
    if (!camera.begin()) {
        Serial.println("Failed to initialize camera");
        return;
    }
    
    Serial.println("Camera initialized");
}

void loop() {
    camera.loop();
} 