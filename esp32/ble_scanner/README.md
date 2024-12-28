# ESP32 BLE Scanner for MAIA

This component provides Bluetooth Low Energy (BLE) scanning capabilities for the MAIA system using ESP32 devices. Multiple scanners can be deployed throughout your space to enable 3D positioning of BLE devices.

## Features

- Continuous BLE device scanning
- MQTT integration for real-time data reporting
- 3D position tracking with multiple scanners
- Configurable scan parameters
- Power management optimizations
- OTA firmware updates
- Web-based configuration interface
- Persistent configuration storage

## Hardware Requirements

- ESP32 development board (ESP32-WROOM-32, ESP32-DevKitC, etc.)
- USB cable for programming
- Power supply (USB or external 5V)
- Optional: 3D-printed case (STL files provided)

## Software Requirements

- Arduino IDE or arduino-cli
- Python 3.7+ (for deployment script)
- Required Arduino libraries:
  - WiFi
  - PubSubClient
  - ArduinoJson
  - ESP32 BLE Arduino

## Installation

1. Install arduino-cli (if not using Arduino IDE):
   ```bash
   curl -fsSL https://raw.githubusercontent.com/arduino/arduino-cli/master/install.sh | sh
   ```

2. Install Python dependencies:
   ```bash
   pip install pyserial
   ```

3. Configure your scanner:
   ```bash
   cp config.json.example config.json
   # Edit config.json with your settings
   ```

4. Deploy firmware:
   ```bash
   python deploy.py --config config.json
   ```

## Configuration

The `config.json` file contains all scanner settings:

```json
{
    "wifi_ssid": "your_wifi_ssid",
    "wifi_password": "your_wifi_password",
    "mqtt_server": "your_mqtt_server",
    "mqtt_user": "your_mqtt_user",
    "mqtt_password": "your_mqtt_password",
    "location": {
        "x": 0.0,
        "y": 0.0,
        "z": 0.0
    },
    "scan_settings": {
        "active_scan": true,
        "filter_duplicates": true,
        "min_rssi": -90
    }
}
```

### Location Calibration

For accurate 3D positioning, each scanner's location must be calibrated:

1. Place scanner in desired location
2. Measure position relative to reference point (0,0,0)
3. Update location in configuration
4. Deploy updated configuration

## MQTT Topics

The scanner publishes to the following MQTT topics:

- `ble_scanner/{device_id}/data` - BLE scan results
- `ble_scanner/{device_id}/status` - Scanner status updates
- `ble_scanner/{device_id}/config` - Configuration updates (subscribe)

### Data Format

Scan results are published as JSON:

```json
{
    "device_mac": "AA:BB:CC:DD:EE:FF",
    "rssi": -65,
    "device_name": "Device Name",
    "metadata": {
        "tx_power": -12,
        "address_type": "public",
        "manufacturer_data": "0201061107"
    }
}
```

## Power Management

The scanner includes several power optimization features:

- WiFi power save mode
- BLE power level adjustment
- Light sleep between scans
- Configurable scan intervals

Enable power saving features in `config.json`:

```json
{
    "power_settings": {
        "light_sleep": true,
        "wifi_power_save": true,
        "ble_power": "high"
    }
}
```

## Troubleshooting

1. Scanner not connecting to WiFi:
   - Check WiFi credentials
   - Ensure 2.4GHz network (ESP32 doesn't support 5GHz)
   - Verify signal strength at scanner location

2. No MQTT messages:
   - Check MQTT broker connection
   - Verify topic permissions
   - Check MQTT credentials

3. Poor scanning performance:
   - Adjust scan parameters
   - Check for interference
   - Consider scanner placement

4. High power consumption:
   - Enable power saving features
   - Adjust scan intervals
   - Check for firmware updates

## Contributing

1. Fork the repository
2. Create a feature branch
3. Commit your changes
4. Push to the branch
5. Create a Pull Request

## License

This project is licensed under the MIT License - see the LICENSE file for details.

## Acknowledgments

- ESP32 BLE library developers
- Arduino community
- MAIA project contributors 