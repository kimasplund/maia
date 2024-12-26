#!/usr/bin/env python3

import sys
import os
import argparse
import json
from pathlib import Path

# Add parent directory to path for seal_tools import
sys.path.append(str(Path(__file__).parent.parent.parent.parent))
from core.seal_tools_integration import SealTools

class AudioCalibrationTool:
    def __init__(self):
        self.seal = SealTools()
        
    def analyze_audio(self, audio_path):
        """Analyze audio for optimal voice detection parameters"""
        try:
            self.seal.log_info(f"Analyzing audio from: {audio_path}")
            analysis = self.seal.analyze_audio(
                audio_path=audio_path,
                analysis_type="voice_detection",
                parameters={
                    "sample_rate": 16000,
                    "bit_depth": 16,
                    "channels": 1
                }
            )
            return analysis
        except Exception as e:
            self.seal.log_error(f"Error analyzing audio: {str(e)}")
            return None

    def calibrate_noise_floor(self, ambient_audio):
        """Calibrate noise floor from ambient audio recording"""
        try:
            self.seal.log_info("Calibrating noise floor")
            calibration = self.seal.analyze_audio(
                audio_path=ambient_audio,
                analysis_type="noise_floor",
                parameters={
                    "duration": 10,  # seconds
                    "sample_count": 1000
                }
            )
            return calibration
        except Exception as e:
            self.seal.log_error(f"Error calibrating noise floor: {str(e)}")
            return None

    def generate_config(self, analysis_results, noise_floor_results, output_file):
        """Generate audio processing configuration"""
        try:
            self.seal.log_info("Generating audio configuration")
            config = {
                "voice_threshold": analysis_results["recommended_threshold"],
                "noise_floor": noise_floor_results["noise_floor_level"],
                "min_duration": analysis_results["recommended_duration"],
                "sample_rate": 16000,
                "bit_depth": 16,
                "buffer_size": analysis_results["recommended_buffer_size"],
                "noise_reduction": {
                    "enabled": True,
                    "level": noise_floor_results["recommended_reduction"]
                }
            }
            
            with open(output_file, 'w') as f:
                json.dump(config, f, indent=2)
            return True
        except Exception as e:
            self.seal.log_error(f"Error generating config: {str(e)}")
            return False

    def validate_config(self, config_file, test_audio):
        """Validate configuration against test audio"""
        try:
            self.seal.log_info("Validating audio configuration")
            with open(config_file, 'r') as f:
                config = json.load(f)
                
            validation = self.seal.validate_config(
                config=config,
                test_data=test_audio,
                validation_type="audio_processing"
            )
            return validation
        except Exception as e:
            self.seal.log_error(f"Error validating config: {str(e)}")
            return None

def main():
    parser = argparse.ArgumentParser(description="Audio Calibration Tool")
    parser.add_argument('--action', choices=['analyze', 'calibrate', 'generate', 'validate'], required=True)
    parser.add_argument('--input', required=True, help="Input audio file")
    parser.add_argument('--ambient', help="Ambient noise recording for calibration")
    parser.add_argument('--output', help="Output configuration file")
    parser.add_argument('--test-audio', help="Test audio for validation")
    
    args = parser.parse_args()
    tool = AudioCalibrationTool()
    
    if args.action == 'analyze':
        results = tool.analyze_audio(args.input)
        if results:
            print(json.dumps(results, indent=2))
            sys.exit(0)
        sys.exit(1)
    
    elif args.action == 'calibrate':
        results = tool.calibrate_noise_floor(args.input)
        if results:
            print(json.dumps(results, indent=2))
            sys.exit(0)
        sys.exit(1)
    
    elif args.action == 'generate':
        if not args.output or not args.ambient:
            print("Error: --output and --ambient required for config generation")
            sys.exit(1)
        
        with open(args.input, 'r') as f:
            analysis_results = json.load(f)
        with open(args.ambient, 'r') as f:
            noise_floor_results = json.load(f)
            
        success = tool.generate_config(analysis_results, noise_floor_results, args.output)
        sys.exit(0 if success else 1)
    
    elif args.action == 'validate':
        if not args.test_audio:
            print("Error: --test-audio required for validation")
            sys.exit(1)
        validation = tool.validate_config(args.input, args.test_audio)
        if validation:
            print(json.dumps(validation, indent=2))
            sys.exit(0)
        sys.exit(1)

if __name__ == "__main__":
    main() 