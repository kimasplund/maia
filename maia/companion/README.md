# MAIA Companion Devices and External Streams

This directory contains the implementation for MAIA companion devices and external stream integration.

## ESP32 Devices

The `esp32` directory contains implementations for three types of companion devices:

1. **ESP32-S Scanner** (`scanner/scanner.ino`)
   - BLE and WiFi scanning capabilities
   - Constant data feeding to Home Assistant
   - Room presence detection

2. **ESP32-CAM** (`camera/camera.ino`)
   - Video streaming capabilities
   - Motion detection
   - Image capture on demand

3. **ESP8266MOD 12-F Voice** (`voice/voice.ino`)
   - Audio streaming capabilities
   - Sound level monitoring
   - Voice activity detection

### Building and Flashing

1. Install PlatformIO
2. Navigate to the `esp32` directory
3. Build and upload:
   ```bash
   # For scanner
   pio run -e scanner -t upload
   
   # For camera
   pio run -e camera -t upload
   
   # For voice
   pio run -e voice -t upload
   ```

## External Stream Integration

MAIA supports integration with external video and audio streams, such as IP cameras or other streaming sources.

### Supported Stream Types

- **Video Streams**
  - RTSP
  - HTTP(S) Live Streaming (HLS)
  - MJPEG
  - WebRTC

- **Audio Streams**
  - HTTP(S) Audio streams
  - WebSocket audio streams
  - RTSP audio

### Authentication Methods

- No authentication
- Basic authentication (username/password)
- Bearer token authentication

### Adding External Streams

1. Navigate to the Devices page in the MAIA web interface
2. Click "Add External Stream"
3. Fill in the stream details:
   - Name: A friendly name for the stream
   - URL: The stream URL
   - Type: Video or Audio
   - Authentication: None, Basic, or Token
   - Authentication details (if required)

### Stream Health Monitoring

MAIA automatically monitors the health of external streams:
- Checks stream availability every minute
- Updates stream status (online/offline)
- Logs any connection issues
- Provides detailed health information in the UI

### Stream Configuration Examples

1. **IP Camera (RTSP)**
   ```
   Name: Living Room Camera
   URL: rtsp://192.168.1.100:554/stream
   Type: video
   Auth: Basic
   Username: admin
   Password: password
   ```

2. **Web Camera (MJPEG)**
   ```
   Name: Garden Camera
   URL: http://192.168.1.101:8080/video
   Type: video
   Auth: None
   ```

3. **Audio Stream**
   ```
   Name: Kitchen Microphone
   URL: http://192.168.1.102:8000/audio
   Type: audio
   Auth: Token
   Token: your_auth_token
   ```

### Integration with Home Assistant

External streams are automatically integrated with Home Assistant:
- Streams appear as camera/media_player entities
- Stream status is reported
- Stream controls (if supported by the source)
- Motion detection events (for video streams)
- Sound detection events (for audio streams)

### Troubleshooting

1. **Stream Not Connecting**
   - Verify the stream URL is correct
   - Check network connectivity
   - Verify authentication credentials
   - Check if the stream source is online

2. **Poor Performance**
   - Check network bandwidth
   - Reduce stream quality if possible
   - Verify hardware decoding is enabled

3. **Authentication Issues**
   - Double-check credentials
   - Verify authentication method is correct
   - Check for special characters in credentials

## Device Management

The MAIA web interface provides a unified management page for all devices and streams:

- Device/stream status monitoring
- Configuration management
- Room assignment
- Capability overview
- Firmware updates (for ESP32 devices)
- Stream health monitoring
- Authentication management

## API Integration

MAIA provides a REST API for managing devices and streams:

```http
# List all devices
GET /api/devices

# Add external stream
POST /api/streams
Content-Type: application/json

{
    "name": "Living Room Camera",
    "url": "rtsp://192.168.1.100:554/stream",
    "type": "video",
    "auth_type": "basic",
    "auth_data": {
        "username": "admin",
        "password": "password"
    }
}

# Get stream details
GET /api/streams/{stream_id}

# Update stream configuration
PUT /api/streams/{stream_id}

# Remove stream
DELETE /api/streams/{stream_id}

# Check stream health
POST /api/streams/{stream_id}/check
```

## Contributing

1. Fork the repository
2. Create a feature branch
3. Commit your changes
4. Push to the branch
5. Create a Pull Request

## License

This project is licensed under the MIT License - see the LICENSE file for details. 