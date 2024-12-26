#include "audio_processor.h"
#include "esp_timer.h"
#include <math.h>

AudioProcessor::AudioProcessor()
    : _initialized(false)
    , _streaming(false)
    , _voice_detection_enabled(false)
    , _noise_reduction_enabled(false)
    , _voice_threshold(VOICE_DETECTION_THRESHOLD)
    , _noise_samples(NOISE_FLOOR_SAMPLES)
    , _voice_duration_threshold(VOICE_DURATION_THRESHOLD)
    , _audio_queue(NULL)
    , _process_buffer(NULL)
    , _buffer_size(BUFFER_SIZE)
    , _voice_detected(false)
    , _voice_start_time(0)
    , _voice_duration(0)
    , _current_audio_level(0)
    , _noise_floor_level(0)
    , _process_task_handle(NULL) {
}

AudioProcessor::~AudioProcessor() {
    stop();
    cleanupResources();
}

bool AudioProcessor::begin() {
    if (_initialized) {
        return true;
    }
    
    if (!initI2S() || !initProcessing()) {
        cleanupResources();
        return false;
    }
    
    _initialized = true;
    return true;
}

bool AudioProcessor::initI2S() {
    _i2s_config = {
        .mode = (i2s_mode_t)(I2S_MODE_MASTER | I2S_MODE_RX),
        .sample_rate = SAMPLE_RATE,
        .bits_per_sample = (i2s_bits_per_sample_t)BITS_PER_SAMPLE,
        .channel_format = I2S_CHANNEL_FMT_ONLY_LEFT,
        .communication_format = I2S_COMM_FORMAT_I2S,
        .intr_alloc_flags = ESP_INTR_FLAG_LEVEL1,
        .dma_buf_count = DMA_BUFFER_COUNT,
        .dma_buf_len = BUFFER_SIZE,
        .use_apll = false
    };
    
    _pin_config = {
        .bck_io_num = I2S_SCK_PIN,
        .ws_io_num = I2S_WS_PIN,
        .data_out_num = I2S_PIN_NO_CHANGE,
        .data_in_num = I2S_SD_PIN
    };
    
    esp_err_t err = i2s_driver_install(I2S_NUM_0, &_i2s_config, 0, NULL);
    if (err != ESP_OK) {
        if (DEBUG_ENABLED) {
            Serial.printf("Failed to install I2S driver: %d\n", err);
        }
        return false;
    }
    
    err = i2s_set_pin(I2S_NUM_0, &_pin_config);
    if (err != ESP_OK) {
        if (DEBUG_ENABLED) {
            Serial.printf("Failed to set I2S pins: %d\n", err);
        }
        return false;
    }
    
    return true;
}

bool AudioProcessor::initProcessing() {
    _audio_queue = xQueueCreate(DMA_BUFFER_COUNT, sizeof(uint8_t*));
    if (!_audio_queue) {
        if (DEBUG_ENABLED) {
            Serial.println("Failed to create audio queue");
        }
        return false;
    }
    
    _process_buffer = (uint8_t*)malloc(BUFFER_SIZE);
    if (!_process_buffer) {
        if (DEBUG_ENABLED) {
            Serial.println("Failed to allocate process buffer");
        }
        return false;
    }
    
    return true;
}

void AudioProcessor::cleanupResources() {
    if (_audio_queue) {
        uint8_t* buffer;
        while (xQueueReceive(_audio_queue, &buffer, 0) == pdTRUE) {
            free(buffer);
        }
        vQueueDelete(_audio_queue);
        _audio_queue = NULL;
    }
    
    if (_process_buffer) {
        free(_process_buffer);
        _process_buffer = NULL;
    }
    
    i2s_driver_uninstall(I2S_NUM_0);
    _initialized = false;
}

bool AudioProcessor::start() {
    if (!_initialized || _streaming) {
        return false;
    }
    
    xTaskCreatePinnedToCore(
        processTask,
        "AudioProcess",
        4096,
        this,
        1,
        &_process_task_handle,
        0
    );
    
    _streaming = true;
    return true;
}

bool AudioProcessor::stop() {
    if (!_streaming) {
        return false;
    }
    
    _streaming = false;
    if (_process_task_handle) {
        vTaskDelete(_process_task_handle);
        _process_task_handle = NULL;
    }
    
    return true;
}

void AudioProcessor::processTask(void* parameter) {
    AudioProcessor* processor = (AudioProcessor*)parameter;
    size_t bytes_read = 0;
    
    while (processor->_streaming) {
        i2s_read(I2S_NUM_0, processor->_process_buffer, BUFFER_SIZE, &bytes_read, portMAX_DELAY);
        
        if (bytes_read > 0) {
            processor->processAudioBuffer(processor->_process_buffer, bytes_read);
            
            if (processor->_streaming) {
                uint8_t* buffer = (uint8_t*)malloc(bytes_read);
                if (buffer) {
                    memcpy(buffer, processor->_process_buffer, bytes_read);
                    if (xQueueSend(processor->_audio_queue, &buffer, 0) != pdTRUE) {
                        free(buffer);
                    }
                }
            }
        }
        
        vTaskDelay(1);
    }
    
    vTaskDelete(NULL);
}

void AudioProcessor::processAudioBuffer(const uint8_t* buffer, size_t size) {
    float level = calculateAudioLevel(buffer, size);
    
    if (_noise_reduction_enabled) {
        level = applyNoiseReduction(level);
    }
    
    _current_audio_level = level;
    
    if (_voice_detection_enabled) {
        updateVoiceDetection(level);
    }
}

float AudioProcessor::calculateAudioLevel(const uint8_t* buffer, size_t size) {
    if (!buffer || size == 0) {
        return 0.0f;
    }
    
    float sum = 0.0f;
    const int16_t* samples = (const int16_t*)buffer;
    size_t sample_count = size / 2;  // 16-bit samples
    
    for (size_t i = 0; i < sample_count; i++) {
        float sample = samples[i] / 32768.0f;  // Normalize to [-1, 1]
        sum += sample * sample;
    }
    
    return sqrt(sum / sample_count);  // RMS value
}

void AudioProcessor::updateVoiceDetection(float level) {
    uint32_t current_time = esp_timer_get_time() / 1000;  // Convert to ms
    
    if (level > _voice_threshold) {
        if (!_voice_detected) {
            _voice_detected = true;
            _voice_start_time = current_time;
        }
        _voice_duration = current_time - _voice_start_time;
    } else {
        if (_voice_detected && (current_time - _voice_start_time) > _voice_duration_threshold) {
            _voice_detected = false;
            _voice_duration = 0;
        }
    }
}

float AudioProcessor::applyNoiseReduction(float level) {
    return level > _noise_floor_level ? level - _noise_floor_level : 0.0f;
}

void AudioProcessor::calibrateNoiseFloor() {
    if (!_initialized || !_streaming) {
        return;
    }
    
    float sum = 0.0f;
    int samples = 0;
    uint32_t start_time = esp_timer_get_time() / 1000;
    
    while (samples < _noise_samples) {
        size_t bytes_read = 0;
        i2s_read(I2S_NUM_0, _process_buffer, BUFFER_SIZE, &bytes_read, portMAX_DELAY);
        
        if (bytes_read > 0) {
            float level = calculateAudioLevel(_process_buffer, bytes_read);
            sum += level;
            samples++;
        }
        
        // Timeout after 5 seconds
        if ((esp_timer_get_time() / 1000) - start_time > 5000) {
            break;
        }
    }
    
    if (samples > 0) {
        _noise_floor_level = sum / samples;
    }
}

bool AudioProcessor::getAudioData(uint8_t* buffer, size_t* size) {
    if (!buffer || !size || !_audio_queue) {
        return false;
    }
    
    uint8_t* queued_buffer;
    if (xQueueReceive(_audio_queue, &queued_buffer, 0) == pdTRUE) {
        memcpy(buffer, queued_buffer, BUFFER_SIZE);
        *size = BUFFER_SIZE;
        free(queued_buffer);
        return true;
    }
    
    return false;
}

bool AudioProcessor::clearAudioBuffer() {
    if (!_audio_queue) {
        return false;
    }
    
    uint8_t* buffer;
    while (xQueueReceive(_audio_queue, &buffer, 0) == pdTRUE) {
        free(buffer);
    }
    
    return true;
}

// Getters and setters
bool AudioProcessor::isStreaming() const { return _streaming; }
void AudioProcessor::setStreaming(bool enable) {
    if (enable) start();
    else stop();
}

bool AudioProcessor::isVoiceDetectionEnabled() const { return _voice_detection_enabled; }
void AudioProcessor::setVoiceDetectionEnabled(bool enable) { _voice_detection_enabled = enable; }

void AudioProcessor::setVoiceThreshold(uint32_t threshold) { _voice_threshold = threshold; }
void AudioProcessor::setNoiseSamples(uint32_t samples) { _noise_samples = samples; }
void AudioProcessor::setVoiceDurationThreshold(uint32_t ms) { _voice_duration_threshold = ms; }

uint32_t AudioProcessor::getVoiceThreshold() const { return _voice_threshold; }
uint32_t AudioProcessor::getNoiseSamples() const { return _noise_samples; }
uint32_t AudioProcessor::getVoiceDurationThreshold() const { return _voice_duration_threshold; }

bool AudioProcessor::isVoiceDetected() const { return _voice_detected; }
uint32_t AudioProcessor::getVoiceDuration() const { return _voice_duration; }
float AudioProcessor::getAudioLevel() const { return _current_audio_level; }

void AudioProcessor::enableNoiseReduction(bool enable) { _noise_reduction_enabled = enable; }
bool AudioProcessor::isNoiseReductionEnabled() const { return _noise_reduction_enabled; } 