#ifndef MOTION_DETECTOR_H
#define MOTION_DETECTOR_H

#include "esp_camera.h"
#include <vector>
#include "config.h"

// Motion detection parameters
#define MOTION_GRID_COLS 32
#define MOTION_GRID_ROWS 24
#define MOTION_THRESHOLD 30        // Pixel difference threshold (0-255)
#define MOTION_SENSITIVITY 20      // Percentage of changed pixels to trigger motion (0-100)
#define MOTION_COOLDOWN 1000      // Minimum time between detections (ms)
#define MOTION_HISTORY_SIZE 10    // Number of frames to keep in history
#define MOTION_ZONES_MAX 8        // Maximum number of motion detection zones

struct MotionZone {
    uint16_t x;          // Zone start X coordinate (0-100%)
    uint16_t y;          // Zone start Y coordinate (0-100%)
    uint16_t width;      // Zone width (0-100%)
    uint16_t height;     // Zone height (0-100%)
    bool enabled;        // Zone enabled state
    uint8_t sensitivity; // Zone-specific sensitivity
};

class MotionDetector {
public:
    MotionDetector();
    ~MotionDetector();
    
    // Initialize motion detection
    bool begin();
    
    // Process frame for motion
    bool detectMotion(camera_fb_t* fb);
    
    // Motion detection control
    void enable(bool enable);
    bool isEnabled() const;
    
    // Motion detection parameters
    void setThreshold(uint8_t threshold);
    void setSensitivity(uint8_t sensitivity);
    void setCooldown(uint32_t ms);
    
    // Get current parameters
    uint8_t getThreshold() const;
    uint8_t getSensitivity() const;
    uint32_t getCooldown() const;
    
    // Motion detection status
    bool isMotionDetected() const;
    uint32_t getLastMotionTime() const;
    float getMotionMagnitude() const;
    
    // Motion zones management
    bool addZone(const MotionZone& zone);
    bool removeZone(uint8_t index);
    bool updateZone(uint8_t index, const MotionZone& zone);
    bool getZone(uint8_t index, MotionZone& zone) const;
    uint8_t getZoneCount() const;
    void clearZones();
    
    // Motion history
    const std::vector<float>& getMotionHistory() const;
    void clearHistory();

private:
    // Motion detection state
    bool _enabled;
    bool _motion_detected;
    uint32_t _last_motion_time;
    float _motion_magnitude;
    
    // Motion detection parameters
    uint8_t _threshold;
    uint8_t _sensitivity;
    uint32_t _cooldown;
    
    // Motion detection grid
    uint8_t* _current_frame;
    uint8_t* _previous_frame;
    size_t _frame_size;
    uint16_t _grid_width;
    uint16_t _grid_height;
    
    // Motion zones
    std::vector<MotionZone> _zones;
    
    // Motion history
    std::vector<float> _motion_history;
    
    // Internal processing methods
    bool initializeFrameBuffers(uint16_t width, uint16_t height);
    void cleanupFrameBuffers();
    bool convertFrameToGrayscale(camera_fb_t* fb, uint8_t* output);
    bool downscaleFrame(const uint8_t* input, uint8_t* output, 
                       uint16_t input_width, uint16_t input_height);
    float calculateFrameDifference();
    bool isMotionInZones(const std::vector<std::pair<uint16_t, uint16_t>>& motion_pixels);
    void updateMotionHistory(float magnitude);
    std::vector<std::pair<uint16_t, uint16_t>> findMotionPixels();
    bool isPixelInZone(uint16_t x, uint16_t y, const MotionZone& zone);
};

#endif // MOTION_DETECTOR_H 