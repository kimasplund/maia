#!/usr/bin/env python3

import sys
import os
import argparse
import json
from pathlib import Path

# Add parent directory to path for seal_tools import
sys.path.append(str(Path(__file__).parent.parent.parent.parent))
from core.seal_tools_integration import SealTools

class FaceRecognitionTool:
    def __init__(self):
        self.seal = SealTools()
        
    def train_model(self, images_dir, output_model):
        """Train face recognition model using provided images"""
        try:
            # Use SEAL's ML capabilities for training
            self.seal.log_info(f"Training face recognition model with images from {images_dir}")
            model_data = self.seal.train_ml_model(
                data_path=images_dir,
                model_type="face_recognition",
                output_path=output_model
            )
            return True
        except Exception as e:
            self.seal.log_error(f"Error training model: {str(e)}")
            return False

    def convert_model(self, input_model, output_file):
        """Convert trained model to ESP32 compatible format"""
        try:
            self.seal.log_info("Converting model to ESP32 format")
            self.seal.convert_model(
                input_path=input_model,
                output_path=output_file,
                target_platform="esp32"
            )
            return True
        except Exception as e:
            self.seal.log_error(f"Error converting model: {str(e)}")
            return False

    def analyze_performance(self, model_path, test_images):
        """Analyze model performance on test images"""
        try:
            self.seal.log_info("Analyzing model performance")
            metrics = self.seal.analyze_ml_model(
                model_path=model_path,
                test_data=test_images
            )
            return metrics
        except Exception as e:
            self.seal.log_error(f"Error analyzing model: {str(e)}")
            return None

def main():
    parser = argparse.ArgumentParser(description="Face Recognition Model Tool")
    parser.add_argument('--action', choices=['train', 'convert', 'analyze'], required=True)
    parser.add_argument('--input', required=True, help="Input directory/file")
    parser.add_argument('--output', required=True, help="Output file")
    parser.add_argument('--test-data', help="Test images directory for analysis")
    
    args = parser.parse_args()
    tool = FaceRecognitionTool()
    
    if args.action == 'train':
        success = tool.train_model(args.input, args.output)
        sys.exit(0 if success else 1)
    
    elif args.action == 'convert':
        success = tool.convert_model(args.input, args.output)
        sys.exit(0 if success else 1)
    
    elif args.action == 'analyze':
        if not args.test_data:
            print("Error: --test-data required for analysis")
            sys.exit(1)
        metrics = tool.analyze_performance(args.input, args.test_data)
        if metrics:
            print(json.dumps(metrics, indent=2))
            sys.exit(0)
        sys.exit(1)

if __name__ == "__main__":
    main() 