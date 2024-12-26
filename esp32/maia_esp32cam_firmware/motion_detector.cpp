#include "motion_detector.h"
#include "esp_timer.h"
#include <algorithm>
#include <cstring>
#include <cmath>

MotionDetector::MotionDetector()
    : _enabled(false)
    , _motion_detected(false)
    , _last_motion_time(0)
    , _motion_magnitude(0)
    , _threshold(MOTION_THRESHOLD)
    , _sensitivity(MOTION_SENSITIVITY)
    , _cooldown(MOTION_COOLDOWN)
    , _current_frame(nullptr)
    , _previous_frame(nullptr)
    , _frame_size(0)
    , _grid_width(MOTION_GRID_COLS)
    , _grid_height(MOTION_GRID_ROWS) {
    _motion_history.reserve(MOTION_HISTORY_SIZE);
}

MotionDetector::~MotionDetector() {
    cleanupFrameBuffers();
}

bool MotionDetector::begin() {
    if (!initializeFrameBuffers(_grid_width, _grid_height)) {
        if (DEBUG_ENABLED) {
            Serial.println("Failed to initialize motion detection buffers");
        }
        return false;
    }
    
    _enabled = true;
    return true;
}

bool MotionDetector::initializeFrameBuffers(uint16_t width, uint16_t height) {
    cleanupFrameBuffers();
    
    _frame_size = width * height;
    _current_frame = (uint8_t*)malloc(_frame_size);
    _previous_frame = (uint8_t*)malloc(_frame_size);
    
    if (!_current_frame || !_previous_frame) {
        cleanupFrameBuffers();
        return false;
    }
    
    memset(_current_frame, 0, _frame_size);
    memset(_previous_frame, 0, _frame_size);
    
    return true;
}

void MotionDetector::cleanupFrameBuffers() {
    if (_current_frame) {
        free(_current_frame);
        _current_frame = nullptr;
    }
    
    if (_previous_frame) {
        free(_previous_frame);
        _previous_frame = nullptr;
    }
    
    _frame_size = 0;
}

bool MotionDetector::detectMotion(camera_fb_t* fb) {
    if (!_enabled || !fb || !_current_frame || !_previous_frame) {
        return false;
    }
    
    // Copy current frame to previous
    memcpy(_previous_frame, _current_frame, _frame_size);
    
    // Convert and downscale new frame
    if (!convertFrameToGrayscale(fb, _current_frame)) {
        return false;
    }
    
    // Calculate frame difference
    float difference = calculateFrameDifference();
    updateMotionHistory(difference);
    
    // Check if motion is detected
    uint32_t current_time = esp_timer_get_time() / 1000;
    if (difference > _sensitivity && 
        (current_time - _last_motion_time) > _cooldown) {
        
        // Check if motion is in defined zones
        auto motion_pixels = findMotionPixels();
        if (_zones.empty() || isMotionInZones(motion_pixels)) {
            _motion_detected = true;
            _last_motion_time = current_time;
            _motion_magnitude = difference;
            return true;
        }
    }
    
    _motion_detected = false;
    return false;
}

bool MotionDetector::convertFrameToGrayscale(camera_fb_t* fb, uint8_t* output) {
    if (!fb || !output) {
        return false;
    }
    
    // Create temporary buffer for full resolution grayscale
    uint8_t* temp_buffer = (uint8_t*)malloc(fb->width * fb->height);
    if (!temp_buffer) {
        return false;
    }
    
    // Convert to grayscale based on format
    if (fb->format == PIXFORMAT_JPEG) {
        // TODO: Implement JPEG to grayscale conversion
        free(temp_buffer);
        return false;
    } else if (fb->format == PIXFORMAT_RGB565) {
        uint16_t* rgb = (uint16_t*)fb->buf;
        for (size_t i = 0; i < fb->width * fb->height; i++) {
            uint16_t pixel = rgb[i];
            uint8_t r = (pixel >> 11) & 0x1F;
            uint8_t g = (pixel >> 5) & 0x3F;
            uint8_t b = pixel & 0x1F;
            temp_buffer[i] = (r * 77 + g * 150 + b * 29) >> 8;
        }
    } else if (fb->format == PIXFORMAT_RGB888) {
        uint8_t* rgb = fb->buf;
        for (size_t i = 0; i < fb->width * fb->height; i++) {
            size_t j = i * 3;
            temp_buffer[i] = (rgb[j] * 77 + rgb[j+1] * 150 + rgb[j+2] * 29) >> 8;
        }
    } else {
        free(temp_buffer);
        return false;
    }
    
    // Downscale to motion detection grid
    bool result = downscaleFrame(temp_buffer, output, fb->width, fb->height);
    free(temp_buffer);
    
    return result;
}

bool MotionDetector::downscaleFrame(const uint8_t* input, uint8_t* output,
                                  uint16_t input_width, uint16_t input_height) {
    if (!input || !output) {
        return false;
    }
    
    float x_ratio = (float)input_width / _grid_width;
    float y_ratio = (float)input_height / _grid_height;
    
    for (uint16_t y = 0; y < _grid_height; y++) {
        for (uint16_t x = 0; x < _grid_width; x++) {
            uint16_t px = (uint16_t)(x * x_ratio);
            uint16_t py = (uint16_t)(y * y_ratio);
            output[y * _grid_width + x] = input[py * input_width + px];
        }
    }
    
    return true;
}

float MotionDetector::calculateFrameDifference() {
    if (!_current_frame || !_previous_frame) {
        return 0.0f;
    }
    
    uint32_t diff_sum = 0;
    uint32_t diff_count = 0;
    
    for (size_t i = 0; i < _frame_size; i++) {
        int16_t diff = abs(_current_frame[i] - _previous_frame[i]);
        if (diff > _threshold) {
            diff_sum += diff;
            diff_count++;
        }
    }
    
    return diff_count > 0 ? 
        (float)(diff_count * 100) / _frame_size : 0.0f;
}

std::vector<std::pair<uint16_t, uint16_t>> MotionDetector::findMotionPixels() {
    std::vector<std::pair<uint16_t, uint16_t>> motion_pixels;
    
    for (uint16_t y = 0; y < _grid_height; y++) {
        for (uint16_t x = 0; x < _grid_width; x++) {
            size_t idx = y * _grid_width + x;
            int16_t diff = abs(_current_frame[idx] - _previous_frame[idx]);
            
            if (diff > _threshold) {
                motion_pixels.push_back(std::make_pair(x, y));
            }
        }
    }
    
    return motion_pixels;
}

bool MotionDetector::isMotionInZones(
    const std::vector<std::pair<uint16_t, uint16_t>>& motion_pixels) {
    
    if (_zones.empty() || motion_pixels.empty()) {
        return true;
    }
    
    for (const auto& pixel : motion_pixels) {
        for (const auto& zone : _zones) {
            if (zone.enabled && isPixelInZone(pixel.first, pixel.second, zone)) {
                return true;
            }
        }
    }
    
    return false;
}

bool MotionDetector::isPixelInZone(uint16_t x, uint16_t y, const MotionZone& zone) {
    float px = (float)x * 100 / _grid_width;
    float py = (float)y * 100 / _grid_height;
    
    return px >= zone.x && px < (zone.x + zone.width) &&
           py >= zone.y && py < (zone.y + zone.height);
}

void MotionDetector::updateMotionHistory(float magnitude) {
    _motion_history.push_back(magnitude);
    
    while (_motion_history.size() > MOTION_HISTORY_SIZE) {
        _motion_history.erase(_motion_history.begin());
    }
}

// Motion zones management
bool MotionDetector::addZone(const MotionZone& zone) {
    if (_zones.size() >= MOTION_ZONES_MAX) {
        return false;
    }
    
    _zones.push_back(zone);
    return true;
}

bool MotionDetector::removeZone(uint8_t index) {
    if (index >= _zones.size()) {
        return false;
    }
    
    _zones.erase(_zones.begin() + index);
    return true;
}

bool MotionDetector::updateZone(uint8_t index, const MotionZone& zone) {
    if (index >= _zones.size()) {
        return false;
    }
    
    _zones[index] = zone;
    return true;
}

bool MotionDetector::getZone(uint8_t index, MotionZone& zone) const {
    if (index >= _zones.size()) {
        return false;
    }
    
    zone = _zones[index];
    return true;
}

uint8_t MotionDetector::getZoneCount() const {
    return _zones.size();
}

void MotionDetector::clearZones() {
    _zones.clear();
}

// Getters and setters
void MotionDetector::enable(bool enable) { _enabled = enable; }
bool MotionDetector::isEnabled() const { return _enabled; }

void MotionDetector::setThreshold(uint8_t threshold) { _threshold = threshold; }
void MotionDetector::setSensitivity(uint8_t sensitivity) { _sensitivity = sensitivity; }
void MotionDetector::setCooldown(uint32_t ms) { _cooldown = ms; }

uint8_t MotionDetector::getThreshold() const { return _threshold; }
uint8_t MotionDetector::getSensitivity() const { return _sensitivity; }
uint32_t MotionDetector::getCooldown() const { return _cooldown; }

bool MotionDetector::isMotionDetected() const { return _motion_detected; }
uint32_t MotionDetector::getLastMotionTime() const { return _last_motion_time; }
float MotionDetector::getMotionMagnitude() const { return _motion_magnitude; }

const std::vector<float>& MotionDetector::getMotionHistory() const {
    return _motion_history;
}

void MotionDetector::clearHistory() {
    _motion_history.clear();
} 