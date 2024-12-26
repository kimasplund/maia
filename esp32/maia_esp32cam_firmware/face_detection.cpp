#include "face_detection.h"
#include <esp_timer.h>
#include <esp_log.h>
#include <cstring>
#include <algorithm>
#include "mbedtls/md.h"

static const char* TAG = "FaceDetection";

bool FaceDetection::begin(const FaceDetectionConfig& config) {
    _config = config;
    
    // Configure face detection
    _mtmn_config.type = FAST_MODE;
    _mtmn_config.min_face = 80;
    _mtmn_config.pyramid = 0.7;
    _mtmn_config.pyramid_times = 4;
    _mtmn_config.p_threshold.score = 0.6;
    _mtmn_config.p_threshold.nms = 0.7;
    _mtmn_config.p_threshold.candidate_number = 20;
    _mtmn_config.r_threshold.score = 0.7;
    _mtmn_config.r_threshold.nms = 0.7;
    _mtmn_config.r_threshold.candidate_number = 10;
    _mtmn_config.o_threshold.score = 0.7;
    _mtmn_config.o_threshold.nms = 0.7;
    _mtmn_config.o_threshold.candidate_number = 1;
    
    return true;
}

bool FaceDetection::detectFaces(camera_fb_t* fb, FaceDetectionResult* result) {
    if (!fb || !result) return false;
    
    // Generate cache key from image data
    std::string cache_key = _generateCacheKey(fb->buf, fb->len);
    
    // Check cache first
    if (_checkCacheEntry(cache_key, result)) {
        _updateCacheMetrics(true);
        return true;
    }
    
    _updateCacheMetrics(false);
    
    // Perform face detection
    box_array_t* boxes = NULL;
    if (dl_detect_face(fb->buf, fb->width, fb->height, &_mtmn_config, &boxes) != ESP_OK) {
        ESP_LOGE(TAG, "Face detection failed");
        return false;
    }
    
    // Process detection results
    result->faces = boxes ? boxes->len : 0;
    result->has_landmarks = _config.detect_landmarks;
    
    if (result->faces > 0) {
        // Store face boxes
        result->boxes.resize(boxes->len);
        result->confidences.resize(boxes->len);
        
        for (int i = 0; i < boxes->len; i++) {
            result->boxes[i] = boxes->box[i];
            result->confidences[i] = boxes->score[i];
        }
        
        // Get landmarks if enabled
        if (_config.detect_landmarks) {
            result->landmarks.resize(boxes->len);
            result->landmark_count = 5; // 5 points per face
            
            for (int i = 0; i < boxes->len; i++) {
                std::vector<point_t> face_landmarks;
                if (dl_detect_face_landmarks(fb->buf, fb->width, fb->height, 
                                          &boxes->box[i], &face_landmarks) == ESP_OK) {
                    result->landmarks[i] = face_landmarks;
                }
            }
        }
        
        // Cache the results
        _storeCacheEntry(cache_key, *result);
    }
    
    // Cleanup
    if (boxes) {
        free(boxes);
    }
    
    // Perform cache maintenance
    _cleanupCache();
    
    return true;
}

std::string FaceDetection::_generateCacheKey(const uint8_t* image_data, size_t length) {
    // Use MD5 for quick image hashing
    unsigned char hash[16];
    char hash_str[33];
    
    mbedtls_md_context_t ctx;
    mbedtls_md_init(&ctx);
    mbedtls_md_setup(&ctx, mbedtls_md_info_from_type(MBEDTLS_MD_MD5), 0);
    mbedtls_md_starts(&ctx);
    mbedtls_md_update(&ctx, image_data, length);
    mbedtls_md_finish(&ctx, hash);
    mbedtls_md_free(&ctx);
    
    // Convert hash to string
    for (int i = 0; i < 16; i++) {
        sprintf(hash_str + (i * 2), "%02x", hash[i]);
    }
    hash_str[32] = '\0';
    
    return std::string(hash_str);
}

bool FaceDetection::_checkCacheEntry(const std::string& key, FaceDetectionResult* result) {
    auto it = _face_cache.find(key);
    if (it == _face_cache.end()) {
        return false;
    }
    
    // Check if cache entry is still valid
    uint32_t now = esp_timer_get_time() / 1000;
    if (now - it->second.timestamp > _config.cache_ttl) {
        _face_cache.erase(it);
        return false;
    }
    
    // Copy cached result
    result->faces = 1;
    result->has_landmarks = it->second.has_landmarks;
    result->confidences = {it->second.confidence};
    
    if (it->second.has_landmarks) {
        result->landmarks.resize(1);
        result->landmarks[0].clear();
        for (const auto& landmark : it->second.landmarks) {
            point_t pt = {landmark.first, landmark.second};
            result->landmarks[0].push_back(pt);
        }
        result->landmark_count = it->second.landmarks.size();
    }
    
    return true;
}

void FaceDetection::_storeCacheEntry(const std::string& key, const FaceDetectionResult& result) {
    // Remove oldest entries if cache is full
    while (_face_cache.size() >= _config.max_cache_size) {
        auto oldest = std::min_element(_face_cache.begin(), _face_cache.end(),
            [](const auto& a, const auto& b) {
                return a.second.timestamp < b.second.timestamp;
            });
        _face_cache.erase(oldest);
    }
    
    // Store new entry
    FaceCache cache_entry;
    cache_entry.timestamp = esp_timer_get_time() / 1000;
    cache_entry.confidence = result.confidences[0];
    cache_entry.has_landmarks = result.has_landmarks;
    
    if (result.has_landmarks && !result.landmarks.empty()) {
        for (const auto& pt : result.landmarks[0]) {
            cache_entry.landmarks.push_back({pt.x, pt.y});
        }
    }
    
    _face_cache[key] = cache_entry;
}

void FaceDetection::_cleanupCache() {
    uint32_t now = esp_timer_get_time() / 1000;
    
    // Only cleanup periodically
    if (now - _last_cache_cleanup < CACHE_CLEANUP_INTERVAL) {
        return;
    }
    
    _last_cache_cleanup = now;
    
    // Remove expired entries
    for (auto it = _face_cache.begin(); it != _face_cache.end();) {
        if (now - it->second.timestamp > _config.cache_ttl) {
            it = _face_cache.erase(it);
        } else {
            ++it;
        }
    }
}

void FaceDetection::clearCache() {
    _face_cache.clear();
    _cache_hits = 0;
    _cache_misses = 0;
    _last_cache_cleanup = 0;
}

float FaceDetection::getCacheHitRate() const {
    uint32_t total = _cache_hits + _cache_misses;
    return total > 0 ? (_cache_hits * 100.0f) / total : 0.0f;
}

void FaceDetection::_updateCacheMetrics(bool cache_hit) {
    if (cache_hit) {
        _cache_hits++;
    } else {
        _cache_misses++;
    }
} 