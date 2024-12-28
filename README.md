# MAIA - Multi-modal AI Assistant

MAIA is a multi-modal AI assistant that integrates with Home Assistant to provide face recognition, voice recognition, and device tracking capabilities.

## Standalone Setup

### Prerequisites
- Docker and Docker Compose
- Home Assistant instance (can be running anywhere accessible via HTTP)
- Home Assistant Long-Lived Access Token

### Quick Start

1. Clone the repository:
   ```bash
   git clone https://github.com/kimasplund/ha_maia.git
   cd ha_maia
   ```

2. Create configuration files:
   ```bash
   # Copy environment template
   cp .env.example .env

   # Create Mosquitto configuration directory
   mkdir -p config/mosquitto
   
   # Set up Mosquitto password
   cd config/mosquitto
   ./setup-mosquitto.sh
   cd ../..
   ```

3. Edit the `.env` file:
   - Set `HA_TOKEN` to your Home Assistant Long-Lived Access Token
   - Set `HA_URL` to your Home Assistant instance URL
   - Modify other settings as needed

4. Start the services:
   ```bash
   docker-compose up -d
   ```

5. Access the web interface:
   - Open `http://localhost:8080` in your browser
   - Log in using your Home Assistant Long-Lived Access Token

### Services

The standalone setup includes:
- MAIA web interface and API (port 8080)
- PostgreSQL database (port 5432)
- Mosquitto MQTT broker (ports 1883, 9001)
- Redis for caching (port 6379)

### Configuration

#### Home Assistant Integration
1. Create a Long-Lived Access Token in Home Assistant:
   - Profile > Long-Lived Access Tokens > Create Token
   - Copy the token and add it to your `.env` file

2. MAIA will automatically:
   - Register itself as a device in Home Assistant
   - Create entities for detected faces, voices, and devices
   - Send real-time updates via MQTT

#### ESP32 Companion Devices
MAIA supports various ESP32 devices for extended functionality:
- ESP32-S: BLE and WiFi scanning
- ESP32-CAM: Image capture and streaming
- ESP8266MOD 12-F: Audio processing

See the `companion/esp32` directory for device-specific code and setup instructions.

### Development

To build and run for development:
```bash
# Start dependencies
docker-compose up -d postgres mosquitto redis

# Install Python dependencies
pip install -r requirements.txt

# Run the application
python run.py
```

### License
MIT License - See LICENSE file for details.

### Author
Kim Asplund (kim.asplund@gmail.com)
Website: https://asplund.kim 