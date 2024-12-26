# MAIA - Advanced Home Assistant Voice and Vision Integration
Version 1.2.0

[![Open your Home Assistant instance and show the add add-on repository dialog with a specific repository URL pre-filled.](https://my.home-assistant.io/badges/supervisor_add_addon_repository.svg)](https://my.home-assistant.io/redirect/supervisor_add_addon_repository/?repository_url=https%3A%2F%2Fgithub.com%2Fkimasplund%2Fmaia)

### Version Changes (1.1.0 → 1.2.0)
- **OpenCV Integration**: Updated to OpenCV 4.10.0+ with enhanced vision processing
- **Face Recognition**: Improved accuracy and performance with latest dlib integration
- **Hardware Acceleration**: Added CUDA and OpenCL support for GPU acceleration
- **Vision Processing**: Enhanced capabilities for real-time video analysis
- **Performance Optimization**: Improved multi-threading and batch processing
- **Text-to-Speech**: Enhanced TTS capabilities with pyttsx3 2.90+
- **Dependencies**: Updated all core dependencies to latest stable versions

MAIA is an extensive Home Assistant module that provides advanced voice and vision processing capabilities, including voice commands, facial recognition, and intelligent automation using the Seal Tools framework.

## Features

### Core Features
- **Voice Processing**
  - Real-time voice command processing from ESP32 devices and other microphones
  - Support for both local processing and OpenAI-powered advanced voice mode
  - Command history and learning from corrections
  - Noise reduction and audio enhancement

- **Vision Processing**
  - Real-time facial recognition for user verification
  - Camera feed monitoring
  - Face database management and training
  - Support for multiple camera sources
  - Motion detection with configurable zones

- **Intelligent Automation**
  - Integration with Seal Tools for command optimization
  - Learning from user feedback and corrections
  - Performance monitoring and automatic optimization
  - Context-aware command processing

### Web Interface
Access the comprehensive web interface at `http://homeassistant:8123/maia/dashboard`

- **Dashboard**
  - System statistics and health monitoring
  - Recent activity feed
  - Active users overview
  - Performance metrics visualization

- **Users Management**
  - User profiles and permissions
  - Face recognition data management
  - Activity tracking
  - Access control settings

- **Commands History**
  - Complete command log
  - Success/failure analysis
  - Pattern recognition
  - User interaction tracking

- **Analytics**
  - SEAL Tools performance metrics
  - System optimization status
  - Resource usage monitoring
  - Trend analysis

- **Settings**
  - System configuration
  - Device management
  - Integration options
  - Security settings

### Tools
Located in the `/tools` directory:

- **Device Control Tool** (`ha_device_control_tool.py`)
  - Device discovery and management
  - Automation creation
  - Scene management
  - Script generation
  - Configuration validation

- **Automation Tool** (`ha_automation_tool.py`)
  - Motion detection automations
  - Face recognition triggers
  - Voice command automations
  - Time-based scenes
  - Presence-based scenes
  - Adaptive lighting control

### Voice Processing
- **Speech Recognition**
  - Real-time voice command processing
  - Multiple engine support
  - Noise reduction and enhancement

- **Text-to-Speech (TTS)**
  - Cross-platform TTS support via pyttsx3
  - Multiple synthesizer support:
    - sapi5 - Windows
    - nsss - macOS
    - espeak - Linux/Unix
  - Voice customization:
    - Rate control
    - Volume adjustment
    - Voice selection
    - Language selection
  - Asynchronous speech generation
  - Event handling for word/sentence boundaries
  - Speech output to file capability

### TTS Configuration
```yaml
# configuration.yaml
maia:
  tts:
    engine: "sapi5"  # or "nsss" for macOS, "espeak" for Linux
    rate: 200        # Words per minute
    volume: 1.0      # 0.0 to 1.0
    voice: "default" # System voice to use
    language: "en"   # Language code
```

### TTS Usage Examples
```python
import pyttsx3
from maia.voice import TTSManager

class MAIATTSEngine:
    def __init__(self):
        self.engine = pyttsx3.init()
        self._configure_engine()

    def _configure_engine(self):
        # Get current properties
        rate = self.engine.getProperty('rate')
        volume = self.engine.getProperty('volume')
        voices = self.engine.getProperty('voices')
        
        # Configure default properties
        self.engine.setProperty('rate', 150)    # Default speaking rate
        self.engine.setProperty('volume', 0.9)  # Default volume
        if voices:  # Set default voice if available
            self.engine.setProperty('voice', voices[0].id)

    def speak(self, text, wait=True):
        """Speak text, optionally wait for completion."""
        if wait:
            self.engine.say(text)
            self.engine.runAndWait()
        else:
            self.engine.startLoop(False)
            self.engine.say(text)
            self.engine.endLoop()

    def save_to_file(self, text, filename):
        """Save speech to file."""
        self.engine.save_to_file(text, filename)
        self.engine.runAndWait()

    def set_voice(self, voice_id):
        """Set voice by ID."""
        self.engine.setProperty('voice', voice_id)

    def get_voices(self):
        """Get list of available voices."""
        return self.engine.getProperty('voices')

    def set_rate(self, rate):
        """Set speaking rate (words per minute)."""
        self.engine.setProperty('rate', rate)

    def set_volume(self, volume):
        """Set volume (0.0 to 1.0)."""
        self.engine.setProperty('volume', volume)

    def add_pronunciation(self, word, pronunciation):
        """Add custom word pronunciation."""
        self.engine.setProperty('voice', {word: pronunciation})

# Usage example
if __name__ == "__main__":
    tts = MAIATTSEngine()
    
    # Basic usage
    tts.speak("Welcome to MAIA")
    
    # Async speech
    tts.speak("Processing your request", wait=False)
    
    # Change voice
    voices = tts.get_voices()
    if len(voices) > 1:
        tts.set_voice(voices[1].id)
    
    # Adjust properties
    tts.set_rate(130)  # Slower
    tts.set_volume(0.8)  # 80% volume
    
    # Save to file
    tts.save_to_file("Welcome to MAIA", "welcome.mp3")
    
    # Custom pronunciation
    tts.add_pronunciation("MAIA", "M A I A")
```

### TTS Configuration in Home Assistant
```yaml
# configuration.yaml
maia:
  tts:
    engine: "pyttsx3"
    default_voice: null  # Will use system default
    default_rate: 150
    default_volume: 0.9
    custom_pronunciations:
      MAIA: "M A I A"
      HAL: "H A L"
    save_directory: "tts_cache"  # For saved audio files
    async_mode: false  # Whether to use async speech by default
```

## Architecture

### Processing Distribution

#### ESP32-CAM Device
- **Initial Processing**
  - Basic motion detection
  - Audio/video capture and streaming
  - Voice activity detection (VAD)
  - Basic face detection (presence only)
  - Data compression and transmission
  - Audio preprocessing and noise reduction

#### Home Assistant (Main Processing)
- **Advanced Processing**
  - Full face recognition and identification
  - Voice command recognition using multiple engines:
    - CMU Sphinx (offline processing)
    - Google Speech Recognition
    - OpenAI Whisper (offline or API)
    - Vosk API (offline)
    - Azure Speech
    - Other supported engines (configurable)
  - Machine learning model execution
  - Complex automation logic
  - Data storage and analysis
  - User management and authentication

### Data Flow
1. ESP32-CAM captures audio/video data
2. Basic processing on ESP32-CAM for efficiency:
   - Motion detection to trigger recordings
   - Voice activity detection to trigger audio capture
   - Face presence detection to trigger face recognition
   - Audio preprocessing (noise reduction, normalization)
3. Data streamed to Home Assistant via WebSocket
4. Home Assistant performs advanced processing:
   - Full face recognition against user database
   - Voice command processing through selected engine
   - Command interpretation and validation
   - Automation execution based on results

### Processing Modes

#### Voice Recognition Modes
- **Offline Mode**
  - Uses CMU Sphinx, Vosk, or local Whisper
  - Complete privacy, no internet required
  - Suitable for basic commands
  - Lower accuracy but faster response

- **Online Mode**
  - Uses Google Speech, OpenAI Whisper API, or Azure
  - Higher accuracy and broader language support
  - Requires internet connection
  - Better handling of complex commands

#### Face Recognition Modes
- **Local Mode** (Default)
  - Face recognition done locally in Home Assistant
  - Suitable for most use cases
  - Privacy-focused

- **Advanced Mode** (Optional)
  - Additional ML model optimizations
  - Enhanced recognition accuracy
  - Requires more computational resources

### Voice Recognition Features
- Multiple engine support for different needs
- Language detection and multilingual support
- Noise reduction and audio enhancement
- Continuous learning from corrections
- Command history and pattern recognition
- Configurable confidence thresholds
- Energy level calibration for ambient noise

## Installation

1. Clone the repository:
```bash
git clone https://github.com/kimasplund/maia.git
cd maia
```

2. Install dependencies:
```bash
pip install -r requirements.txt
```

3. Add to your Home Assistant configuration:
```yaml
# configuration.yaml
maia:
  api_key: "your_openai_api_key"  # Optional
  enable_advanced_voice_mode: false  # Optional
  use_tool_feedback: true  # Optional
```

## ESP32 Setup

### Initial ESP32-CAM Flashing

#### Hardware Requirements
- ESP32-CAM board
- FTDI USB-to-TTL adapter or similar USB-to-Serial programmer
- Jumper wires
- Micro USB cable for power (optional)

#### Wiring for Flashing
1. Connect ESP32-CAM to FTDI adapter:
   - ESP32-CAM GND → FTDI GND
   - ESP32-CAM 5V/VCC → FTDI VCC (3.3V)
   - ESP32-CAM U0R (TX) → FTDI RX
   - ESP32-CAM U0T (RX) → FTDI TX
   - ESP32-CAM IO0 → FTDI GND (only during flashing)

2. Important: GPIO 0 (IO0) must be connected to GND during flashing to enter programming mode

#### Flashing Process
1. Install ESP32 tools:
   ```bash
   pip install esptool
   ```

2. Download the firmware:
   ```bash
   # Clone repository if you haven't already
   git clone https://github.com/kimasplund/maia.git
   cd maia/esp32/maia_esp32cam_firmware
   ```

3. Put ESP32-CAM in flashing mode:
   - Connect IO0 to GND
   - Press the RST button or power cycle the board

4. Flash the firmware:
   ```bash
   esptool.py --port COM5 --baud 115200 --chip esp32 \
     --before default_reset --after hard_reset write_flash -z \
     --flash_mode dio --flash_freq 80m --flash_size detect \
     0x1000 bootloader.bin \
     0x8000 partitions.bin \
     0x10000 maia_esp32cam_firmware.bin
   ```
   Note: Replace `COM5` with your actual serial port (e.g., `/dev/ttyUSB0` on Linux)

5. After flashing:
   - Disconnect IO0 from GND
   - Press RST button or power cycle
   - The board will start in normal mode

#### First-time Configuration
1. On first boot, ESP32-CAM creates a WiFi access point named "MAIA_XXXXX"
2. Connect to this WiFi network
3. Open http://192.168.4.1 in your browser
4. Configure your WiFi credentials and MAIA settings:
   - Home WiFi SSID and password
   - Home Assistant IP address
   - Device name
   - Camera settings (optional)
   - Audio settings (optional)

#### Troubleshooting
- If flashing fails, double-check:
  - Wiring connections
  - IO0 is properly grounded during flashing
  - Correct COM port is selected
  - USB driver is properly installed
- If the board doesn't create WiFi access point:
  - Press and hold RESET for 10 seconds to factory reset
  - Check power supply (ESP32-CAM needs stable 5V)

1. Flash the ESP32 firmware (available in the `esp32` directory)
2. Configure the ESP32 with your WiFi credentials
3. Add the ESP32 device in Home Assistant:
```yaml
# configuration.yaml
maia:
  devices:
    - id: "esp32_living_room"
      ip: "192.168.1.100"
      capabilities: ["audio"]
    - id: "esp32_bedroom"
      ip: "192.168.1.101"
      capabilities: ["audio", "camera"]
```

## Usage

### Voice Commands
MAIA processes voice commands from ESP32 devices or other microphones. Commands are processed locally by default, but can use OpenAI's advanced processing if configured.

Example service call:
```yaml
service: maia.handle_voice_command
data:
  command: "Turn on the living room lights"
  user_id: "john_doe"
```

### Facial Recognition
MAIA verifies users using facial recognition through connected cameras.

Example service call:
```yaml
service: maia.handle_camera_check
data:
  camera_id: "camera.front_door"
  user_id: "john_doe"
```

### Using the Tools

1. Device Control:
```bash
python tools/ha_device_control_tool.py --action discover --ha-url "http://your-ha-instance:8123" --auth-token "your-token"
```

2. Create Motion Automation:
```bash
python tools/ha_automation_tool.py --action motion --camera-id "camera.living_room" --config "motion_config.json" --output "motion_automation.yaml"
```

3. Create Adaptive Lighting:
```bash
python tools/ha_automation_tool.py --action adaptive --entities "lights.json" --config "adaptive_config.json" --output "adaptive_lighting.yaml"
```

## Project Structure

```
maia/
├── __init__.py           # Main module initialization
├── manifest.json         # Module manifest
├── requirements.txt      # Python dependencies
├── const.py             # Constants
├── config_flow.py       # Configuration flow
├── tools/               # Management and configuration tools
│   ├── ha_device_control_tool.py
│   └── ha_automation_tool.py
├── core/                # Core functionality
│   ├── voice_processor.py
│   ├── camera_processor.py
│   ├── openai_integration.py
│   └── seal_tools_integration.py
├── api/                 # API components
│   ├── esp32_client.py
│   └── websocket_handler.py
├── utils/               # Utility functions
│   ├── audio_utils.py
│   ├── image_utils.py
│   └── logging_utils.py
├── database/            # Data storage
│   ├── models.py
│   └── storage.py
├── web/                 # Web dashboard
│   ├── dashboard.py
│   └── static/
└── esp32/              # ESP32 firmware
    └── maia_esp32cam_firmware/
```

## Configuration

### OpenAI Integration
To use advanced voice processing:
1. Get an API key from OpenAI
2. Add to configuration:
```yaml
maia:
  api_key: "your_openai_api_key"
  enable_advanced_voice_mode: true
```

### Face Recognition
To set up facial recognition:
1. Add cameras to your configuration
2. Register user faces through the dashboard
3. Configure recognition settings:
```yaml
maia:
  face_recognition:
    min_confidence: 0.8
    enable_training: true
```

## Development

### Prerequisites
- Python 3.9 or higher
- Home Assistant development environment
- ESP32 development tools (for device firmware)

### Required Dependencies
- **SpeechRecognition** >= 3.12.0 (voice processing)
- **PyAudio** >= 0.2.11 (microphone input)
- **dlib** >= 19.7.0 (face detection and recognition core)
- **face-recognition** == 1.3.0 (face recognition)
- **face-recognition-models** >= 0.3.0 (pre-trained models)
- **opencv-python** >= 4.10.0 (image processing and computer vision)
  - Supports Python 3.6+
  - Pre-built binaries available for:
    - Windows (32/64-bit)
    - macOS (x86_64/ARM64)
    - Linux (x86_64/ARM64)
  - GPU support available through separate opencv-python-cuda package
  - Headless version available (opencv-python-headless) for server environments

### Vision Processing Capabilities
- **Image Processing**
  - Real-time video capture and streaming
  - Image enhancement and preprocessing
  - Color space conversions
  - Image filtering and transformations
  - Contour detection and shape analysis
  
- **Computer Vision Features**
  - Motion detection and tracking
  - Object detection and recognition
  - Image segmentation
  - Feature detection and matching
  - Camera calibration
  - Perspective transformation
  
- **Hardware Acceleration**
  - CUDA support for GPU acceleration
  - OpenCL acceleration
  - Hardware-optimized operations
  - Multi-threading support
  
- **Video Processing**
  - Real-time video analysis
  - Video encoding/decoding
  - Frame extraction and manipulation
  - Video stabilization
  - Background subtraction

### Vision Processing Setup
1. Install OpenCV with pip:
   ```bash
   # Standard installation
   pip install opencv-python>=4.10.0
   
   # For servers without GUI (smaller package)
   pip install opencv-python-headless>=4.10.0
   
   # With extra modules (if needed)
   pip install opencv-contrib-python>=4.10.0
   ```

2. Configure vision processing in MAIA:
   ```yaml
   # configuration.yaml
   maia:
     vision:
       # Camera settings
       camera_resolution: "1280x720"
       frame_rate: 30
       
       # Processing settings
       enable_gpu: true
       enable_threading: true
       thread_count: 4
       
       # Feature settings
       motion_detection: true
       object_detection: false
       face_detection: true
       
       # Performance settings
       processing_scale: 1.0  # Scale factor for processing
       max_processing_threads: 4
       buffer_size: 10  # Frame buffer size
   ```

### Optional Dependencies
- **CMU Sphinx** (offline voice processing)
- **Vosk** (offline voice processing)
- **OpenAI Whisper** (enhanced voice processing)
- **Azure Speech SDK** (cloud voice processing)

### System Requirements
- **Linux/macOS/Windows** supported
- **CUDA-enabled GPU** recommended for faster face recognition
- **C++ build tools** required for dlib installation
- Minimum 4GB RAM recommended

### Face Recognition Features
- Real-time face detection and recognition
- 128-dimensional face encodings
- Support for multiple face detection
- Face landmark detection (68 points)
- Face alignment and normalization
- Batch processing capabilities
- Adjustable tolerance levels
- Recognition accuracy up to 99.38%

### Face Recognition Setup
1. Install system dependencies:
   ```bash
   # Ubuntu/Debian
   sudo apt-get install build-essential cmake pkg-config
   sudo apt-get install libx11-dev libatlas-base-dev
   sudo apt-get install libgtk-3-dev libboost-python-dev
   
   # macOS
   brew install cmake pkg-config
   brew install dlib
   
   # Windows
   # Install Visual Studio Build Tools with C++ support
   ```

2. Install Python dependencies:
   ```bash
   pip install dlib
   pip install face-recognition
   pip install face-recognition-models
   ```

3. Configure face recognition settings:
   ```yaml
   # configuration.yaml
   maia:
     face_recognition:
       min_confidence: 0.6  # Lower = more sensitive
       enable_gpu: true     # Use CUDA if available
       batch_size: 128      # Adjust based on RAM
       enable_landmarks: true
       model_type: "large"  # or "small" for faster processing
   ```

### Setting Up Development Environment
1. Clone the repository
2. Create a virtual environment:
```bash
python -m venv venv
source venv/bin/activate  # Linux/Mac
venv\Scripts\activate     # Windows
```

3. Install development dependencies:
```bash
pip install -r requirements-dev.txt
```

### Running Tests
```bash
pytest tests/
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
- [Seal Tools](https://github.com/fairyshine/Seal-Tools) for the optimization framework
- Home Assistant community for inspiration and support
- OpenAI for advanced voice processing capabilities 

### Face Recognition Implementation
MAIA uses the world's simplest facial recognition API for Python, powered by dlib's state-of-the-art face recognition model with deep learning. Key features include:

#### Core Capabilities
- **Accuracy**: Up to 99.38% on the Labeled Faces in the Wild benchmark
- **Processing Options**: 
  - CPU-based processing for standard deployments
  - GPU acceleration via CUDA for high-performance needs
  - Batch processing support for multiple images
- **Face Detection Models**:
  - HOG-based (default): Fast CPU-based detection
  - CNN-based: More accurate GPU-accelerated detection
- **Feature Detection**: 68-point facial landmark detection
- **Face Encoding**: 128-dimensional face embeddings

#### Command Line Interface
MAIA provides convenient command-line tools for face recognition tasks:

```bash
# Register a new face
maia-tools faces register ./known_people/john.jpg "John Doe"

# Verify faces in an image
maia-tools faces verify ./unknown_picture.jpg

# Adjust recognition sensitivity
maia-tools faces verify --tolerance 0.54 ./unknown_picture.jpg

# Use GPU acceleration
maia-tools faces verify --model cnn ./unknown_picture.jpg

# Process multiple images in parallel
maia-tools faces verify --cpus 4 ./unknown_pictures/
```

#### Python API Usage
```python
from maia.vision import FaceRecognition

# Initialize face recognition
face_rec = FaceRecognition(model="cnn", tolerance=0.6)

# Register a new face
face_rec.register_face("John", "path/to/john.jpg")

# Verify a face
result = face_rec.verify_face("path/to/unknown.jpg")
if result.match:
    print(f"Matched user: {result.user_name}")
```

#### Performance Optimization
- **GPU Acceleration**: Enable CUDA support for up to 10x faster processing
- **Batch Processing**: Process multiple images simultaneously
- **Parallel CPU Processing**: Utilize multiple CPU cores
- **Model Selection**: Choose between speed (HOG) and accuracy (CNN)
- **Memory Management**: Batch size adjustments for resource optimization

#### Integration with Home Assistant
```yaml
# configuration.yaml
maia:
  face_recognition:
    # Recognition settings
    model: "hog"  # or "cnn" for GPU acceleration
    tolerance: 0.6
    min_detection_size: 20
    
    # Performance settings
    batch_size: 128
    num_workers: 4
    use_gpu: false
    
    # Feature settings
    detect_landmarks: true
    detect_attributes: true
    
    # Processing modes
    unknown_face_threshold: 0.8
    remember_unknown_faces: true
    max_unknown_faces: 100
``` 