#include "../base_config.h"
#include <driver/i2s.h>
#include <PubSubClient.h>

// I2S configuration for INMP441 microphone
#define I2S_WS_PIN      25
#define I2S_SCK_PIN     26
#define I2S_SD_PIN      27
#define I2S_PORT        I2S_NUM_0
#define I2S_SAMPLE_RATE 16000
#define I2S_BUFFER_SIZE 512

class VoiceConfig : public BaseConfig {
private:
    WiFiClient wifi_client;
    PubSubClient mqtt_client;
    unsigned long last_sample_time;
    int sample_interval;  // configurable interval in milliseconds
    bool monitoring_enabled;
    int16_t i2s_buffer[I2S_BUFFER_SIZE];
    float noise_threshold;  // configurable noise threshold
    
public:
    VoiceConfig() : mqtt_client(wifi_client), last_sample_time(0), sample_interval(100), 
                   monitoring_enabled(true), noise_threshold(0.1) {}
    
    bool begin() override {
        if (!BaseConfig::begin()) {
            return false;
        }
        
        // Initialize I2S for INMP441 microphone
        esp_err_t err = initI2S();
        if (err != ESP_OK) {
            Serial.printf("Failed to initialize I2S: %d\n", err);
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
        
        return true;
    }
    
    void loop() override {
        if (!mqtt_client.connected()) {
            connectMQTT();
        }
        mqtt_client.loop();
        
        unsigned long now = millis();
        if (now - last_sample_time > sample_interval) {
            processAudio();
            last_sample_time = now;
        }
    }
    
private:
    esp_err_t initI2S() {
        i2s_config_t i2s_config = {
            .mode = (i2s_mode_t)(I2S_MODE_MASTER | I2S_MODE_RX),
            .sample_rate = I2S_SAMPLE_RATE,
            .bits_per_sample = I2S_BITS_PER_SAMPLE_16BIT,
            .channel_format = I2S_CHANNEL_FMT_ONLY_LEFT,
            .communication_format = I2S_COMM_FORMAT_I2S,
            .intr_alloc_flags = ESP_INTR_FLAG_LEVEL1,
            .dma_buf_count = 4,
            .dma_buf_len = I2S_BUFFER_SIZE,
            .use_apll = false,
            .tx_desc_auto_clear = false,
            .fixed_mclk = 0
        };
        
        i2s_pin_config_t pin_config = {
            .bck_io_num = I2S_SCK_PIN,
            .ws_io_num = I2S_WS_PIN,
            .data_out_num = I2S_PIN_NO_CHANGE,
            .data_in_num = I2S_SD_PIN
        };
        
        esp_err_t err = i2s_driver_install(I2S_PORT, &i2s_config, 0, NULL);
        if (err != ESP_OK) return err;
        
        err = i2s_set_pin(I2S_PORT, &pin_config);
        if (err != ESP_OK) return err;
        
        return ESP_OK;
    }
    
    bool connectMQTT() {
        if (!mqtt_client.connected()) {
            String client_id = "MAIA_Voice_" + device_id;
            
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
        
        if (doc.containsKey("sample_interval")) {
            sample_interval = doc["sample_interval"].as<int>();
        }
        if (doc.containsKey("monitoring_enabled")) {
            monitoring_enabled = doc["monitoring_enabled"].as<bool>();
        }
        if (doc.containsKey("noise_threshold")) {
            noise_threshold = doc["noise_threshold"].as<float>();
        }
    }
    
    void processAudio() {
        if (!monitoring_enabled) {
            return;
        }
        
        size_t bytes_read = 0;
        esp_err_t result = i2s_read(I2S_PORT, i2s_buffer, sizeof(i2s_buffer), &bytes_read, portMAX_DELAY);
        
        if (result != ESP_OK) {
            Serial.printf("Failed to read I2S data: %d\n", result);
            return;
        }
        
        if (bytes_read > 0) {
            // Calculate audio metrics
            float rms = 0;
            float peak = 0;
            int samples = bytes_read / sizeof(int16_t);
            
            for (int i = 0; i < samples; i++) {
                float sample = i2s_buffer[i] / 32768.0f;  // Normalize to [-1, 1]
                rms += sample * sample;
                peak = max(peak, abs(sample));
            }
            
            rms = sqrt(rms / samples);
            
            // Create state document
            StaticJsonDocument<256> state;
            state["monitoring"] = monitoring_enabled;
            state["rms_level"] = rms;
            state["peak_level"] = peak;
            state["sample_rate"] = I2S_SAMPLE_RATE;
            
            // Publish via MQTT
            String state_str;
            serializeJson(state, state_str);
            mqtt_client.publish(getMQTTTopic(MQTT_STATE_TOPIC, "voice").c_str(), state_str.c_str(), true);
            
            // If the audio level is significant, publish the raw audio data
            if (rms > noise_threshold) {
                String audio_topic = getMQTTTopic(MQTT_STATE_TOPIC, "voice/audio");
                mqtt_client.publish(audio_topic.c_str(), (uint8_t*)i2s_buffer, bytes_read);
            }
        }
    }
};

VoiceConfig voice;

void setup() {
    Serial.begin(115200);
    Serial.println("MAIA Voice");
    
    // Wait for configuration
    while (!voice.parseConfig(Serial.readStringUntil('\n').c_str())) {
        delay(1000);
    }
    
    if (!voice.begin()) {
        Serial.println("Failed to initialize voice sensor");
        return;
    }
    
    Serial.println("Voice sensor initialized");
}

void loop() {
    voice.loop();
} 