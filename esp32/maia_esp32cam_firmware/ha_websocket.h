#ifndef HA_WEBSOCKET_H
#define HA_WEBSOCKET_H

#include <WebSocketsClient.h>
#include <ArduinoJson.h>
#include <functional>
#include <vector>
#include <string>
#include "config.h"

// WebSocket message types
enum class HAMessageType {
    AUTH_REQUIRED,
    AUTH,
    AUTH_OK,
    AUTH_INVALID,
    RESULT,
    EVENT,
    SUBSCRIBE_EVENTS,
    PING,
    PONG
};

// WebSocket message
struct HAMessage {
    HAMessageType type;
    uint32_t id;
    String payload;
};

// Event callback type
using HAEventCallback = std::function<void(const JsonDocument&)>;

class HAWebSocket {
public:
    HAWebSocket();
    ~HAWebSocket();
    
    // Initialize WebSocket connection
    bool begin();
    
    // Connection management
    bool connect();
    void disconnect();
    bool isConnected() const;
    
    // Message handling
    bool sendMessage(const String& message);
    bool sendBinary(uint8_t* data, size_t len);
    
    // Event subscription
    bool subscribeToEvents(const String& event_type);
    bool unsubscribeFromEvents(const String& event_type);
    
    // Event callbacks
    void onEvent(const String& event_type, HAEventCallback callback);
    void clearEventCallbacks();
    
    // Status reporting
    bool sendStatus(const String& status, const String& message);
    bool sendError(const String& error);
    
    // Authentication
    void setAuthToken(const String& token);
    bool isAuthenticated() const;
    
    // Connection parameters
    void setHost(const String& host);
    void setPort(uint16_t port);
    void setPath(const String& path);
    void setUseSSL(bool use_ssl);
    
    // Reconnection settings
    void setReconnectInterval(uint32_t interval);
    void setMaxReconnectAttempts(uint8_t attempts);
    
    // Message handling
    void loop();

private:
    // WebSocket client
    WebSocketsClient _client;
    
    // Connection state
    bool _connected;
    bool _authenticated;
    uint32_t _last_ping;
    uint32_t _last_reconnect;
    uint8_t _reconnect_attempts;
    
    // Connection parameters
    String _host;
    uint16_t _port;
    String _path;
    String _auth_token;
    bool _use_ssl;
    
    // Reconnection parameters
    uint32_t _reconnect_interval;
    uint8_t _max_reconnect_attempts;
    
    // Message ID counter
    uint32_t _message_id;
    
    // Event subscriptions
    struct EventSubscription {
        String event_type;
        HAEventCallback callback;
    };
    std::vector<EventSubscription> _subscriptions;
    
    // Internal message handling
    void handleWebSocketEvent(WStype_t type, uint8_t* payload, size_t length);
    void handleMessage(const String& message);
    void handleAuthRequired();
    void handleAuthResult(bool success);
    void handleEvent(const JsonDocument& event);
    
    // Message creation helpers
    String createAuthMessage() const;
    String createEventSubscriptionMessage(const String& event_type) const;
    String createStatusMessage(const String& status, const String& message) const;
    
    // Utility functions
    uint32_t getNextMessageId();
    void resetConnection();
    bool parseMessage(const String& message, JsonDocument& doc);
    HAMessageType getMessageType(const String& type);
    
    // Event management
    bool addSubscription(const String& event_type, HAEventCallback callback);
    bool removeSubscription(const String& event_type);
    void notifySubscribers(const String& event_type, const JsonDocument& event);
    
    // Connection management
    void maintainConnection();
    void handleReconnection();
    bool shouldReconnect() const;
    
    // Debug helpers
    void logDebug(const String& message) const;
    void logError(const String& error) const;
};

#endif // HA_WEBSOCKET_H 