#ifndef AUDIO_PROCESSOR_H
#define AUDIO_PROCESSOR_H

#include <driver/i2s.h>
#include <freertos/FreeRTOS.h>
#include <freertos/task.h>
#include <freertos/queue.h>
#include "config.h"

// Audio processing parameters
#define SAMPLE_RATE AUDIO_SAMPLE_RATE
#define BITS_PER_SAMPLE AUDIO_BIT_DEPTH
#define BUFFER_SIZE AUDIO_BUFFER_SIZE
#define DMA_BUFFER_COUNT 8
#define VOICE_DETECTION_THRESHOLD 2000  // Adjust based on testing
#define NOISE_FLOOR_SAMPLES 1000
#define VOICE_DURATION_THRESHOLD 500    // Minimum voice duration in ms

class AudioProcessor {
public:
    AudioProcessor();
    ~AudioProcessor();
    
    // Initialize audio processing
    bool begin();
    
    // Start/stop audio processing
    bool start();
    bool stop();
    
    // Audio stream control
    bool isStreaming() const;
    void setStreaming(bool enable);
    
    // Voice detection control
    bool isVoiceDetectionEnabled() const;
    void setVoiceDetectionEnabled(bool enable);
    
    // Audio processing parameters
    void setVoiceThreshold(uint32_t threshold);
    void setNoiseSamples(uint32_t samples);
    void setVoiceDurationThreshold(uint32_t ms);
    
    // Get current audio parameters
    uint32_t getVoiceThreshold() const;
    uint32_t getNoiseSamples() const;
    uint32_t getVoiceDurationThreshold() const;
    
    // Audio buffer management
    bool getAudioData(uint8_t* buffer, size_t* size);
    bool clearAudioBuffer();
    
    // Voice detection status
    bool isVoiceDetected() const;
    uint32_t getVoiceDuration() const;
    float getAudioLevel() const;
    
    // Noise reduction
    void enableNoiseReduction(bool enable);
    bool isNoiseReductionEnabled() const;
    void calibrateNoiseFloor();

private:
    // I2S configuration
    i2s_config_t _i2s_config;
    i2s_pin_config_t _pin_config;
    
    // Audio processing state
    bool _initialized;
    bool _streaming;
    bool _voice_detection_enabled;
    bool _noise_reduction_enabled;
    
    // Voice detection parameters
    uint32_t _voice_threshold;
    uint32_t _noise_samples;
    uint32_t _voice_duration_threshold;
    
    // Audio processing buffers
    QueueHandle_t _audio_queue;
    uint8_t* _process_buffer;
    size_t _buffer_size;
    
    // Voice detection state
    bool _voice_detected;
    uint32_t _voice_start_time;
    uint32_t _voice_duration;
    float _current_audio_level;
    float _noise_floor_level;
    
    // Audio processing tasks
    TaskHandle_t _process_task_handle;
    static void processTask(void* parameter);
    
    // Internal processing methods
    void processAudioBuffer(const uint8_t* buffer, size_t size);
    float calculateAudioLevel(const uint8_t* buffer, size_t size);
    void updateVoiceDetection(float level);
    float applyNoiseReduction(float level);
    
    // Initialization helpers
    bool initI2S();
    bool initProcessing();
    void cleanupResources();
};

#endif // AUDIO_PROCESSOR_H 