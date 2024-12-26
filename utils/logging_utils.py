"""
Logging utilities for MAIA.
Handles asynchronous logging, monitoring, and error tracking.
"""
import logging
import json
import os
import asyncio
from typing import Dict, Any, Optional
from datetime import datetime
import traceback

class AsyncLogger:
    def __init__(self, name: str):
        self.logger = logging.getLogger(name)
        self.log_dir = "logs"
        self.ensure_log_directory()
        
        # Log file paths
        self.interaction_log = os.path.join(self.log_dir, "interactions.log")
        self.error_log = os.path.join(self.log_dir, "errors.log")
        self.performance_log = os.path.join(self.log_dir, "performance.log")
        
        # Performance monitoring
        self.performance_metrics = {
            'total_interactions': 0,
            'total_errors': 0,
            'average_response_time': 0.0
        }
        
        # Lock for thread-safe logging
        self.log_lock = asyncio.Lock()

    def ensure_log_directory(self):
        """Ensure log directory exists."""
        if not os.path.exists(self.log_dir):
            os.makedirs(self.log_dir)
            
        # Create log files if they don't exist
        for log_file in [self.interaction_log, self.error_log, self.performance_log]:
            if not os.path.exists(log_file):
                with open(log_file, 'w') as f:
                    json.dump([], f)

    async def async_log_interaction(self, component: str, action: str,
                                  input_data: Dict[str, Any],
                                  output_data: Dict[str, Any]) -> None:
        """
        Log an interaction asynchronously.
        
        Args:
            component: Component name
            action: Action performed
            input_data: Input data
            output_data: Output data
        """
        try:
            entry = {
                'timestamp': datetime.now().isoformat(),
                'component': component,
                'action': action,
                'input': input_data,
                'output': output_data
            }
            
            async with self.log_lock:
                await self._append_to_log(self.interaction_log, entry)
                
            # Update metrics
            self.performance_metrics['total_interactions'] += 1
            
        except Exception as e:
            self.logger.error(f"Error logging interaction: {str(e)}")

    async def async_log_error(self, component: str, action: str,
                            error: str, context: Optional[Dict] = None) -> None:
        """
        Log an error asynchronously.
        
        Args:
            component: Component where error occurred
            action: Action that caused error
            error: Error message
            context: Optional context information
        """
        try:
            entry = {
                'timestamp': datetime.now().isoformat(),
                'component': component,
                'action': action,
                'error': error,
                'traceback': traceback.format_exc(),
                'context': context or {}
            }
            
            async with self.log_lock:
                await self._append_to_log(self.error_log, entry)
                
            # Update metrics
            self.performance_metrics['total_errors'] += 1
            
            # Log to system logger as well
            self.logger.error(f"{component}.{action}: {error}")
            
        except Exception as e:
            self.logger.error(f"Error logging error: {str(e)}")

    async def async_log_performance(self, component: str,
                                  metrics: Dict[str, Any]) -> None:
        """
        Log performance metrics asynchronously.
        
        Args:
            component: Component being measured
            metrics: Performance metrics
        """
        try:
            entry = {
                'timestamp': datetime.now().isoformat(),
                'component': component,
                'metrics': metrics
            }
            
            async with self.log_lock:
                await self._append_to_log(self.performance_log, entry)
                
            # Update average response time
            if 'response_time' in metrics:
                current_avg = self.performance_metrics['average_response_time']
                total = self.performance_metrics['total_interactions']
                new_time = metrics['response_time']
                
                self.performance_metrics['average_response_time'] = (
                    (current_avg * total + new_time) / (total + 1)
                )
                
        except Exception as e:
            self.logger.error(f"Error logging performance: {str(e)}")

    async def _append_to_log(self, log_file: str, entry: Dict[str, Any]) -> None:
        """Append entry to log file."""
        try:
            # Read existing log
            with open(log_file, 'r') as f:
                log_data = json.load(f)
                
            # Append new entry
            log_data.append(entry)
            
            # Write back to file
            with open(log_file, 'w') as f:
                json.dump(log_data, f, indent=2)
                
        except Exception as e:
            self.logger.error(f"Error appending to log: {str(e)}")
            raise

    async def get_recent_interactions(self, limit: int = 100) -> list:
        """Get recent interactions from log."""
        try:
            with open(self.interaction_log, 'r') as f:
                data = json.load(f)
            return data[-limit:]
        except Exception as e:
            self.logger.error(f"Error getting recent interactions: {str(e)}")
            return []

    async def get_error_summary(self) -> Dict[str, Any]:
        """Get summary of recent errors."""
        try:
            with open(self.error_log, 'r') as f:
                data = json.load(f)
                
            # Group errors by component
            error_summary = {}
            for entry in data:
                component = entry['component']
                if component not in error_summary:
                    error_summary[component] = {
                        'total_errors': 0,
                        'recent_errors': []
                    }
                    
                error_summary[component]['total_errors'] += 1
                error_summary[component]['recent_errors'].append({
                    'timestamp': entry['timestamp'],
                    'action': entry['action'],
                    'error': entry['error']
                })
                
            return error_summary
            
        except Exception as e:
            self.logger.error(f"Error getting error summary: {str(e)}")
            return {}

    async def get_performance_metrics(self) -> Dict[str, Any]:
        """Get current performance metrics."""
        return {
            'timestamp': datetime.now().isoformat(),
            'metrics': self.performance_metrics
        }

    async def clear_old_logs(self, days: int = 30) -> None:
        """Clear logs older than specified days."""
        try:
            cutoff = datetime.now().timestamp() - (days * 24 * 60 * 60)
            
            for log_file in [self.interaction_log, self.error_log, self.performance_log]:
                with open(log_file, 'r') as f:
                    data = json.load(f)
                    
                # Filter out old entries
                filtered = [
                    entry for entry in data
                    if datetime.fromisoformat(entry['timestamp']).timestamp() > cutoff
                ]
                
                with open(log_file, 'w') as f:
                    json.dump(filtered, f, indent=2)
                    
        except Exception as e:
            self.logger.error(f"Error clearing old logs: {str(e)}")
            raise 