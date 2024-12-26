// Main JavaScript for MAIA web interface

// WebSocket connection
let ws = null;
let wsReconnectAttempts = 0;
const MAX_RECONNECT_ATTEMPTS = 5;
const RECONNECT_DELAY = 5000;

// Initialize WebSocket connection
function initWebSocket() {
    const protocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:';
    const wsUrl = `${protocol}//${window.location.host}/ws`;
    
    ws = new WebSocket(wsUrl);
    
    ws.onopen = () => {
        console.log('WebSocket connected');
        wsReconnectAttempts = 0;
        updateConnectionStatus('connected');
    };
    
    ws.onclose = () => {
        console.log('WebSocket disconnected');
        updateConnectionStatus('disconnected');
        
        // Attempt to reconnect
        if (wsReconnectAttempts < MAX_RECONNECT_ATTEMPTS) {
            setTimeout(() => {
                wsReconnectAttempts++;
                initWebSocket();
            }, RECONNECT_DELAY);
        }
    };
    
    ws.onerror = (error) => {
        console.error('WebSocket error:', error);
        updateConnectionStatus('error');
    };
    
    ws.onmessage = (event) => {
        handleWebSocketMessage(event.data);
    };
}

// Handle WebSocket messages
function handleWebSocketMessage(data) {
    try {
        const message = JSON.parse(data);
        
        // Handle different message types
        switch (message.type) {
            case 'voice':
                handleVoiceMessage(message);
                break;
            case 'camera':
                handleCameraMessage(message);
                break;
            case 'status':
                handleStatusMessage(message);
                break;
            default:
                console.warn('Unknown message type:', message.type);
        }
        
    } catch (error) {
        console.error('Failed to handle message:', error);
    }
}

// Update connection status indicator
function updateConnectionStatus(status) {
    const statusElement = document.getElementById('connection-status');
    if (statusElement) {
        statusElement.className = `status-value status-${status}`;
        statusElement.textContent = status.charAt(0).toUpperCase() + status.slice(1);
    }
}

// Send message through WebSocket
function sendMessage(type, data) {
    if (ws && ws.readyState === WebSocket.OPEN) {
        ws.send(JSON.stringify({ type, data }));
    } else {
        console.warn('WebSocket not connected');
    }
}

// Handle voice messages
function handleVoiceMessage(message) {
    const voiceOutput = document.getElementById('voice-output');
    if (voiceOutput && message.text) {
        // Create message element
        const messageElement = document.createElement('div');
        messageElement.className = 'voice-message';
        messageElement.innerHTML = `
            <span class="timestamp">${new Date().toLocaleTimeString()}</span>
            <span class="text">${message.text}</span>
        `;
        
        // Add to output
        voiceOutput.appendChild(messageElement);
        voiceOutput.scrollTop = voiceOutput.scrollHeight;
    }
}

// Handle camera messages
function handleCameraMessage(message) {
    const cameraOutput = document.getElementById('camera-output');
    if (cameraOutput && message.faces) {
        // Update face detection overlay
        updateFaceOverlay(message.faces);
    }
}

// Handle status messages
function handleStatusMessage(message) {
    const statusElements = {
        api: document.getElementById('api-status'),
        camera: document.getElementById('camera-status'),
        voice: document.getElementById('voice-status'),
        storage: document.getElementById('storage-status')
    };
    
    // Update status indicators
    for (const [key, element] of Object.entries(statusElements)) {
        if (element && message.components && message.components[key]) {
            const status = message.components[key];
            element.className = `status-value status-${status ? 'online' : 'offline'}`;
            element.textContent = status ? 'Online' : 'Offline';
        }
    }
}

// Update face detection overlay
function updateFaceOverlay(faces) {
    const overlay = document.getElementById('face-overlay');
    if (!overlay) return;
    
    // Clear existing overlay
    overlay.innerHTML = '';
    
    // Add face rectangles
    faces.forEach(face => {
        const rect = document.createElement('div');
        rect.className = 'face-rect';
        rect.style.left = `${face.location[3]}px`;
        rect.style.top = `${face.location[0]}px`;
        rect.style.width = `${face.location[1] - face.location[3]}px`;
        rect.style.height = `${face.location[2] - face.location[0]}px`;
        
        // Add name label if face is recognized
        if (face.match && face.match.name) {
            const label = document.createElement('div');
            label.className = 'face-label';
            label.textContent = face.match.name;
            rect.appendChild(label);
        }
        
        overlay.appendChild(rect);
    });
}

// Initialize when DOM is loaded
document.addEventListener('DOMContentLoaded', () => {
    // Initialize WebSocket
    initWebSocket();
    
    // Add event listeners for interactive elements
    const voiceButton = document.getElementById('voice-button');
    if (voiceButton) {
        voiceButton.addEventListener('click', () => {
            // Toggle voice recognition
            const isActive = voiceButton.classList.toggle('active');
            sendMessage('voice', { active: isActive });
        });
    }
    
    const cameraButton = document.getElementById('camera-button');
    if (cameraButton) {
        cameraButton.addEventListener('click', () => {
            // Toggle camera feed
            const isActive = cameraButton.classList.toggle('active');
            sendMessage('camera', { active: isActive });
        });
    }
}); 