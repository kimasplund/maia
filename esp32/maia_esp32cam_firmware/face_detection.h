#pragma once

#include <esp_camera.h>
#include <dl_lib.h>
#include <vector>
#include <string>
#include <unordered_map>
#include <utility>

// Configuration for face detection
struct FaceDetectionConfig {
    bool detect_landmarks = true;
    uint32_t cache_ttl = 1000;        // Cache entry time-to-live in milliseconds
    size_t max_cache_size = 100;      // Maximum number of cached faces
};

// Result structure for face detection
struct FaceDetectionResult {
    int faces = 0;                    // Number of faces detected
    bool has_landmarks = false;       // Whether landmarks were detected
    std::vector<box_t> boxes;         // Bounding boxes for detected faces
    std::vector<float> confidences;   // Confidence scores for detected faces
    std::vector<std::vector<point_t>> landmarks;  // Facial landmarks for each face
    int landmark_count = 0;           // Number of landmarks per face
};

// Cache entry for face detection results
struct FaceCache {
    uint32_t timestamp;              // When this entry was created
    float confidence;                // Detection confidence
    bool has_landmarks;              // Whether landmarks are included
    std::vector<std::pair<float, float>> landmarks;  // Cached landmarks
};

class FaceDetection {
public:
    bool begin(const FaceDetectionConfig& config);
    bool detectFaces(camera_fb_t* fb, FaceDetectionResult* result);
    void clearCache();
    float getCacheHitRate() const;

private:
    static constexpr uint32_t CACHE_CLEANUP_INTERVAL = 10000;  // 10 seconds

    mtmn_config_t _mtmn_config;
    FaceDetectionConfig _config;
    std::unordered_map<std::string, FaceCache> _face_cache;
    
    uint32_t _cache_hits = 0;
    uint32_t _cache_misses = 0;
    uint32_t _last_cache_cleanup = 0;

    std::string _generateCacheKey(const uint8_t* image_data, size_t length);
    bool _checkCacheEntry(const std::string& key, FaceDetectionResult* result);
    void _storeCacheEntry(const std::string& key, const FaceDetectionResult& result);
    void _cleanupCache();
    void _updateCacheMetrics(bool cache_hit);
}; 