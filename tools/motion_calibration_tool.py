#!/usr/bin/env python3

import sys
import os
import argparse
import json
from pathlib import Path

# Add parent directory to path for seal_tools import
sys.path.append(str(Path(__file__).parent.parent.parent.parent))
from core.seal_tools_integration import SealTools

class MotionCalibrationTool:
    def __init__(self):
        self.seal = SealTools()
        
    def analyze_scene(self, video_path):
        """Analyze scene for optimal motion detection parameters"""
        try:
            self.seal.log_info(f"Analyzing scene from video: {video_path}")
            analysis = self.seal.analyze_video(
                video_path=video_path,
                analysis_type="motion_detection",
                parameters={
                    "min_duration": 1000,  # ms
                    "resolution": "VGA",
                    "fps": 20
                }
            )
            return analysis
        except Exception as e:
            self.seal.log_error(f"Error analyzing scene: {str(e)}")
            return None

    def generate_config(self, analysis_results, output_file):
        """Generate motion detection configuration based on analysis"""
        try:
            self.seal.log_info("Generating motion detection configuration")
            config = {
                "threshold": analysis_results["recommended_threshold"],
                "sensitivity": analysis_results["recommended_sensitivity"],
                "zones": analysis_results["recommended_zones"],
                "min_duration": analysis_results["min_duration"],
                "cooldown": analysis_results["recommended_cooldown"]
            }
            
            with open(output_file, 'w') as f:
                json.dump(config, f, indent=2)
            return True
        except Exception as e:
            self.seal.log_error(f"Error generating config: {str(e)}")
            return False

    def validate_config(self, config_file, test_video):
        """Validate configuration against test video"""
        try:
            self.seal.log_info("Validating motion detection configuration")
            with open(config_file, 'r') as f:
                config = json.load(f)
                
            validation = self.seal.validate_config(
                config=config,
                test_data=test_video,
                validation_type="motion_detection"
            )
            return validation
        except Exception as e:
            self.seal.log_error(f"Error validating config: {str(e)}")
            return None

def main():
    parser = argparse.ArgumentParser(description="Motion Detection Calibration Tool")
    parser.add_argument('--action', choices=['analyze', 'generate', 'validate'], required=True)
    parser.add_argument('--input', required=True, help="Input video file or analysis results")
    parser.add_argument('--output', help="Output configuration file")
    parser.add_argument('--test-video', help="Test video for validation")
    
    args = parser.parse_args()
    tool = MotionCalibrationTool()
    
    if args.action == 'analyze':
        results = tool.analyze_scene(args.input)
        if results:
            print(json.dumps(results, indent=2))
            sys.exit(0)
        sys.exit(1)
    
    elif args.action == 'generate':
        if not args.output:
            print("Error: --output required for config generation")
            sys.exit(1)
        with open(args.input, 'r') as f:
            analysis_results = json.load(f)
        success = tool.generate_config(analysis_results, args.output)
        sys.exit(0 if success else 1)
    
    elif args.action == 'validate':
        if not args.test_video:
            print("Error: --test-video required for validation")
            sys.exit(1)
        validation = tool.validate_config(args.input, args.test_video)
        if validation:
            print(json.dumps(validation, indent=2))
            sys.exit(0)
        sys.exit(1)

if __name__ == "__main__":
    main() 