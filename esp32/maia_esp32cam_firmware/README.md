# MAIA ESP32-CAM Firmware

This firmware enables ESP32-CAM modules to work with the MAIA Home Assistant module, providing advanced camera and audio processing capabilities.

## Features

- Real-time video streaming with configurable resolution and quality
- Real-time audio streaming using I2S MEMS microphone
- Face detection and recognition
- Motion detection with configurable zones
- Voice activity detection
- WebSocket communication with Home Assistant
- OTA (Over-The-Air) updates
- Configurable LED status indicators
- Deep sleep support for power saving
- HTTPS support for secure communication

## Hardware Requirements

### Required Components
- ESP32-CAM module (AI Thinker or compatible)
- I2S MEMS microphone (INMP441 or SPH0645)
- FTDI programmer for initial flashing
- 5V power supply

### Optional Components
- External antenna for better WiFi reception
- External LED for status indication
- PIR sensor for motion detection backup

### Pin Connections

#### Camera Module (Pre-wired on ESP32-CAM)
- All camera pins are pre-configured on the ESP32-CAM module

#### I2S Microphone
- WS (Word Select/LRCL): GPIO 15
- SD (Serial Data/DOUT): GPIO 13
- SCK (Serial Clock): GPIO 14
- GND: GND
- VDD: 3.3V

#### Status LED
- Built-in LED: GPIO 33
- Flash LED: GPIO 4

## Software Requirements

### Development Environment
- PlatformIO IDE
- Visual Studio Code (recommended)
- ESP32 development framework
- Git (for version control)

### Required Libraries
- WebSockets (by Links2004)
- ArduinoJson
- ESP32-Camera
- ESP-Face
- ESP32-audioI2S
- FreeRTOS

## Installation

1. Clone the repository:
   ```bash
   git clone https://github.com/yourusername/maia_esp32cam_firmware.git
   cd maia_esp32cam_firmware
   ```

2. Copy the configuration template:
   ```bash
   cp config.h.example config.h
   ```

3. Edit `config.h` with your settings:
   - WiFi credentials
   - Home Assistant connection details
   - Device-specific settings

4. Build and upload using PlatformIO:
   ```bash
   pio run -t upload
   ```

## Configuration

### Camera Settings
```cpp
#define CAMERA_FRAME_SIZE FRAMESIZE_SVGA  // Resolution
#define CAMERA_JPEG_QUALITY 12            // Quality (0-63)
#define VIDEO_FRAME_RATE 20               // FPS
```

### Audio Settings
```cpp
#define AUDIO_SAMPLE_RATE 16000          // Sample rate
#define AUDIO_BIT_DEPTH 16               // Bit depth
#define AUDIO_BUFFER_SIZE 512            // Buffer size
```

### Network Settings
```cpp
#define WIFI_SSID "your_wifi_ssid"
#define WIFI_PASSWORD "your_wifi_password"
#define HA_HOST "192.168.1.100"          // Home Assistant IP
#define HA_PORT 8123                     // Home Assistant port
```

### Feature Settings
```cpp
#define ENABLE_FACE_DETECTION true
#define ENABLE_MOTION_DETECTION true
#define ENABLE_AUDIO_DETECTION true
```

## Integration with Home Assistant

Add to your Home Assistant configuration:
```yaml
maia:
  cameras:
    - platform: maia_camera
      name: "Living Room Camera"
      host: 192.168.1.200
      auth_token: your_auth_token
      features:
        - face_detection
        - motion_detection
        - audio
```

## Usage

### LED Status Indicators
- Fast blink (100ms): Booting
- Double blink: WiFi connecting
- Slow blink (500ms): Normal operation
- Solid: Streaming active
- Quick triple blink: Error state

### Home Assistant Integration
The device will automatically:
1. Connect to WiFi
2. Establish WebSocket connection with Home Assistant
3. Register itself as a camera device
4. Start responding to Home Assistant commands

### Available Commands
- Start/stop video stream
- Start/stop audio stream
- Enable/disable face detection
- Enable/disable motion detection
- Configure motion detection zones
- Adjust camera settings
- Trigger deep sleep mode

## Development

### Project Structure
```
maia_esp32cam_firmware/
├── src/
│   ├── main.cpp
│   ├── face_detection.cpp
│   ├── audio_processor.cpp
│   ├── motion_detector.cpp
│   └── ha_websocket.cpp
├── include/
│   ├── face_detection.h
│   ├── audio_processor.h
│   ├── motion_detector.h
│   └── ha_websocket.h
├── platformio.ini
├── config.h.example
└── README.md
```

### Building
```bash
# Build only
pio run

# Build and upload
pio run -t upload

# Monitor serial output
pio device monitor
```

### OTA Updates
1. Enable OTA in configuration
2. Build firmware
3. Upload using OTA:
   ```bash
   pio run -t upload --upload-port IP_ADDRESS
   ```

## Troubleshooting

### Common Issues

1. Camera Initialization Failed
   - Check camera module connection
   - Verify PSRAM is enabled
   - Try reducing frame size

2. Audio Issues
   - Verify I2S pin connections
   - Check microphone power supply
   - Validate audio configuration

3. WiFi Connection Problems
   - Check credentials
   - Verify signal strength
   - Consider external antenna

4. Memory Issues
   - Reduce frame size/quality
   - Adjust buffer sizes
   - Check heap fragmentation

### Debug Mode
Enable debug output in `config.h`:
```cpp
#define DEBUG_ENABLED true
```

Monitor debug output:
```bash
pio device monitor
```

## Contributing

1. Fork the repository
2. Create a feature branch
3. Commit your changes
4. Push to the branch
5. Create a Pull Request

## License

This project is licensed under the MIT License - see the LICENSE file for details.

## Acknowledgments

- ESP32-CAM community
- Home Assistant community
- MAIA project contributors
- Open source library maintainers 