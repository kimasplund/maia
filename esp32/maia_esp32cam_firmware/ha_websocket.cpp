#include "ha_websocket.h"
#include "esp_timer.h"

HAWebSocket::HAWebSocket()
    : _connected(false)
    , _authenticated(false)
    , _last_ping(0)
    , _last_reconnect(0)
    , _reconnect_attempts(0)
    , _host(HA_HOST)
    , _port(HA_PORT)
    , _path(HA_WS_PATH)
    , _auth_token(AUTH_TOKEN)
    , _use_ssl(ENABLE_HTTPS)
    , _reconnect_interval(WEBSOCKET_RECONNECT_INTERVAL)
    , _max_reconnect_attempts(MAX_RECONNECT_ATTEMPTS)
    , _message_id(1) {
}

HAWebSocket::~HAWebSocket() {
    disconnect();
}

bool HAWebSocket::begin() {
    _client.onEvent([this](WStype_t type, uint8_t* payload, size_t length) {
        this->handleWebSocketEvent(type, payload, length);
    });
    
    return connect();
}

bool HAWebSocket::connect() {
    if (_connected) {
        return true;
    }
    
    if (_use_ssl) {
        _client.beginSSL(_host.c_str(), _port, _path.c_str());
    } else {
        _client.begin(_host.c_str(), _port, _path.c_str());
    }
    
    _client.setReconnectInterval(_reconnect_interval);
    return true;
}

void HAWebSocket::disconnect() {
    _client.disconnect();
    resetConnection();
}

void HAWebSocket::resetConnection() {
    _connected = false;
    _authenticated = false;
    _last_ping = 0;
    _reconnect_attempts = 0;
    clearEventCallbacks();
}

void HAWebSocket::loop() {
    _client.loop();
    maintainConnection();
}

void HAWebSocket::maintainConnection() {
    uint32_t now = esp_timer_get_time() / 1000;  // Convert to ms
    
    if (_connected) {
        // Send periodic pings
        if (now - _last_ping > WEBSOCKET_PING_INTERVAL) {
            _client.sendPing();
            _last_ping = now;
        }
    } else if (shouldReconnect()) {
        handleReconnection();
    }
}

bool HAWebSocket::shouldReconnect() const {
    if (!_connected && _reconnect_attempts < _max_reconnect_attempts) {
        uint32_t now = esp_timer_get_time() / 1000;
        return (now - _last_reconnect) > _reconnect_interval;
    }
    return false;
}

void HAWebSocket::handleReconnection() {
    _last_reconnect = esp_timer_get_time() / 1000;
    _reconnect_attempts++;
    
    if (DEBUG_ENABLED) {
        logDebug("Attempting reconnection " + String(_reconnect_attempts) + 
                 " of " + String(_max_reconnect_attempts));
    }
    
    connect();
}

void HAWebSocket::handleWebSocketEvent(WStype_t type, uint8_t* payload, size_t length) {
    switch (type) {
        case WStype_DISCONNECTED:
            _connected = false;
            _authenticated = false;
            if (DEBUG_ENABLED) {
                logDebug("Disconnected from Home Assistant");
            }
            break;
            
        case WStype_CONNECTED:
            _connected = true;
            _reconnect_attempts = 0;
            if (DEBUG_ENABLED) {
                logDebug("Connected to Home Assistant");
            }
            break;
            
        case WStype_TEXT:
            if (length > 0) {
                handleMessage(String((char*)payload));
            }
            break;
            
        case WStype_PING:
            _client.sendPong();
            break;
            
        case WStype_PONG:
            _last_ping = esp_timer_get_time() / 1000;
            break;
            
        default:
            break;
    }
}

void HAWebSocket::handleMessage(const String& message) {
    StaticJsonDocument<JSON_BUFFER_SIZE> doc;
    if (!parseMessage(message, doc)) {
        return;
    }
    
    const char* type = doc["type"];
    if (!type) {
        return;
    }
    
    HAMessageType msg_type = getMessageType(type);
    
    switch (msg_type) {
        case HAMessageType::AUTH_REQUIRED:
            handleAuthRequired();
            break;
            
        case HAMessageType::AUTH_OK:
            handleAuthResult(true);
            break;
            
        case HAMessageType::AUTH_INVALID:
            handleAuthResult(false);
            break;
            
        case HAMessageType::EVENT:
            handleEvent(doc);
            break;
            
        default:
            break;
    }
}

void HAWebSocket::handleAuthRequired() {
    String auth_message = createAuthMessage();
    sendMessage(auth_message);
}

void HAWebSocket::handleAuthResult(bool success) {
    _authenticated = success;
    
    if (success) {
        if (DEBUG_ENABLED) {
            logDebug("Successfully authenticated with Home Assistant");
        }
        
        // Resubscribe to events
        for (const auto& sub : _subscriptions) {
            subscribeToEvents(sub.event_type);
        }
    } else {
        if (DEBUG_ENABLED) {
            logError("Authentication failed");
        }
        disconnect();
    }
}

void HAWebSocket::handleEvent(const JsonDocument& event) {
    const char* event_type = event["event"]["event_type"];
    if (!event_type) {
        return;
    }
    
    notifySubscribers(event_type, event);
}

bool HAWebSocket::sendMessage(const String& message) {
    if (!_connected) {
        return false;
    }
    
    return _client.sendTXT(message);
}

bool HAWebSocket::sendBinary(uint8_t* data, size_t len) {
    if (!_connected) {
        return false;
    }
    
    return _client.sendBIN(data, len);
}

bool HAWebSocket::sendStatus(const String& status, const String& message) {
    return sendMessage(createStatusMessage(status, message));
}

bool HAWebSocket::sendError(const String& error) {
    StaticJsonDocument<JSON_BUFFER_SIZE> doc;
    doc["type"] = "error";
    doc["error"] = error;
    
    String message;
    serializeJson(doc, message);
    return sendMessage(message);
}

bool HAWebSocket::subscribeToEvents(const String& event_type) {
    if (!_authenticated) {
        return false;
    }
    
    String message = createEventSubscriptionMessage(event_type);
    return sendMessage(message);
}

bool HAWebSocket::unsubscribeFromEvents(const String& event_type) {
    return removeSubscription(event_type);
}

void HAWebSocket::onEvent(const String& event_type, HAEventCallback callback) {
    addSubscription(event_type, callback);
}

void HAWebSocket::clearEventCallbacks() {
    _subscriptions.clear();
}

String HAWebSocket::createAuthMessage() const {
    StaticJsonDocument<JSON_BUFFER_SIZE> doc;
    doc["type"] = "auth";
    doc["access_token"] = _auth_token;
    
    String message;
    serializeJson(doc, message);
    return message;
}

String HAWebSocket::createEventSubscriptionMessage(const String& event_type) const {
    StaticJsonDocument<JSON_BUFFER_SIZE> doc;
    doc["id"] = getNextMessageId();
    doc["type"] = "subscribe_events";
    if (event_type.length() > 0) {
        doc["event_type"] = event_type;
    }
    
    String message;
    serializeJson(doc, message);
    return message;
}

String HAWebSocket::createStatusMessage(const String& status, const String& message) const {
    StaticJsonDocument<JSON_BUFFER_SIZE> doc;
    doc["type"] = "status";
    doc["id"] = getNextMessageId();
    doc["status"] = status;
    doc["message"] = message;
    
    String result;
    serializeJson(doc, result);
    return result;
}

uint32_t HAWebSocket::getNextMessageId() {
    return _message_id++;
}

bool HAWebSocket::parseMessage(const String& message, JsonDocument& doc) {
    DeserializationError error = deserializeJson(doc, message);
    
    if (error) {
        if (DEBUG_ENABLED) {
            logError("JSON parsing failed: " + String(error.c_str()));
        }
        return false;
    }
    
    return true;
}

HAMessageType HAWebSocket::getMessageType(const String& type) {
    if (type == "auth_required") return HAMessageType::AUTH_REQUIRED;
    if (type == "auth") return HAMessageType::AUTH;
    if (type == "auth_ok") return HAMessageType::AUTH_OK;
    if (type == "auth_invalid") return HAMessageType::AUTH_INVALID;
    if (type == "result") return HAMessageType::RESULT;
    if (type == "event") return HAMessageType::EVENT;
    if (type == "subscribe_events") return HAMessageType::SUBSCRIBE_EVENTS;
    if (type == "ping") return HAMessageType::PING;
    if (type == "pong") return HAMessageType::PONG;
    
    return HAMessageType::RESULT;  // Default
}

bool HAWebSocket::addSubscription(const String& event_type, HAEventCallback callback) {
    // Check if already subscribed
    for (auto& sub : _subscriptions) {
        if (sub.event_type == event_type) {
            sub.callback = callback;
            return true;
        }
    }
    
    // Add new subscription
    EventSubscription sub = {event_type, callback};
    _subscriptions.push_back(sub);
    
    // If already authenticated, subscribe immediately
    if (_authenticated) {
        return subscribeToEvents(event_type);
    }
    
    return true;
}

bool HAWebSocket::removeSubscription(const String& event_type) {
    for (auto it = _subscriptions.begin(); it != _subscriptions.end(); ++it) {
        if (it->event_type == event_type) {
            _subscriptions.erase(it);
            return true;
        }
    }
    return false;
}

void HAWebSocket::notifySubscribers(const String& event_type, const JsonDocument& event) {
    for (const auto& sub : _subscriptions) {
        if (sub.event_type == event_type || sub.event_type.length() == 0) {
            sub.callback(event);
        }
    }
}

// Getters and setters
bool HAWebSocket::isConnected() const { return _connected; }
bool HAWebSocket::isAuthenticated() const { return _authenticated; }

void HAWebSocket::setAuthToken(const String& token) { _auth_token = token; }
void HAWebSocket::setHost(const String& host) { _host = host; }
void HAWebSocket::setPort(uint16_t port) { _port = port; }
void HAWebSocket::setPath(const String& path) { _path = path; }
void HAWebSocket::setUseSSL(bool use_ssl) { _use_ssl = use_ssl; }
void HAWebSocket::setReconnectInterval(uint32_t interval) { _reconnect_interval = interval; }
void HAWebSocket::setMaxReconnectAttempts(uint8_t attempts) { _max_reconnect_attempts = attempts; }

void HAWebSocket::logDebug(const String& message) const {
    if (DEBUG_ENABLED) {
        Serial.println("HAWebSocket: " + message);
    }
}

void HAWebSocket::logError(const String& error) const {
    if (DEBUG_ENABLED) {
        Serial.println("HAWebSocket Error: " + error);
    }
} 