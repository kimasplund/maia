# MAIA - My AI Assistant

MAIA (My AI Assistant) is an advanced Home Assistant add-on that provides voice control and computer vision capabilities. It integrates seamlessly with your Home Assistant installation to enable natural voice commands and face recognition for enhanced home automation.

## Features

- **Voice Control**: Natural language voice commands for controlling your home automation
- **Face Recognition**: Real-time face detection and recognition for personalized automation
- **Web Interface**: Modern and responsive web interface for easy management
- **OpenAI Integration**: Enhanced natural language understanding using OpenAI's GPT models
- **Multi-language Support**: Support for multiple languages in voice recognition
- **Customizable**: Extensive configuration options to match your needs

## Installation

1. Add the MAIA repository to your Home Assistant add-on store:
   ```
   https://github.com/kimasplund/maia
   ```

2. Install the MAIA add-on from the add-on store

3. Configure the add-on settings:
   - Set up voice recognition preferences
   - Configure camera settings
   - Adjust system performance settings

4. Start the add-on

## Configuration

The add-on can be configured through the Home Assistant UI. Available options include:

### Camera Settings
- `model_type`: Face detection model type (HOG or CNN)
- `use_gpu`: Enable GPU acceleration if available
- `tolerance`: Face recognition tolerance (0.0-1.0)
- `batch_processing`: Enable batch processing for better performance
- `thread_limits`: Control thread usage for processing

### Voice Settings
- `recognition_engine`: Choose between different speech recognition engines
- `language`: Set recognition language
- `enable_noise_reduction`: Enable background noise reduction
- `thread_limits`: Control thread usage for audio processing

### System Settings
- `websocket.host`: WebSocket server host
- `websocket.port`: WebSocket server port
- `database.host`: Redis database host
- `database.port`: Redis database port

## Usage

### Voice Commands
1. Open the MAIA web interface
2. Click the microphone button to start voice recognition
3. Speak your command naturally
4. MAIA will process and execute the command

### Face Recognition
1. Navigate to the Faces section
2. Register faces for family members
3. Enable face detection in the camera view
4. MAIA will recognize registered faces and trigger automations

## Development

### Prerequisites
- Python 3.8 or higher
- Redis server
- Development packages for audio and video processing

### Setup Development Environment
1. Clone the repository:
   ```bash
   git clone https://github.com/kimasplund/maia.git
   cd maia
   ```

2. Create a virtual environment:
   ```bash
   python -m venv venv
   source venv/bin/activate  # Linux/macOS
   venv\Scripts\activate     # Windows
   ```

3. Install dependencies:
   ```bash
   pip install -r requirements.txt
   ```

4. Run the application:
   ```bash
   python main.py
   ```

### Testing
Run the test suite:
```bash
pytest
```

## Contributing

1. Fork the repository
2. Create a feature branch
3. Commit your changes
4. Push to the branch
5. Create a Pull Request

## License

This project is licensed under the MIT License - see the LICENSE file for details.

## Support

- Report issues on GitHub
- Join our Discord community
- Check the documentation for detailed information

## Acknowledgments

- Home Assistant community
- OpenAI for GPT integration
- Face Recognition library contributors
- All our contributors and users 