"""
Seal Tools integration module for MAIA.
Handles tool feedback and optimization using the Seal Tools framework.
"""
import time
import json
import os
from typing import Dict, List, Any, Optional
from datetime import datetime
import asyncio
import logging
from seal_tools import SealClient, SealOptimizer, SealFeedback
from ..utils.logging_utils import AsyncLogger

_LOGGER = logging.getLogger(__name__)

class SealToolsIntegration:
    def __init__(self, enabled: bool = True):
        self.enabled = enabled
        self.logger = AsyncLogger(__name__)
        
        # Initialize Seal Tools components
        self.seal_client = SealClient()
        self.optimizer = SealOptimizer()
        self.feedback_handler = SealFeedback()
        
        # Feedback storage
        self.feedback_log = "tool_feedback_log.json"
        self._ensure_log_file()
        
        # Optimization settings
        self.optimization_interval = 3600  # 1 hour
        self.last_optimization = None
        self.min_feedback_count = 50
        
        # Performance metrics
        self.metrics = {
            'total_feedback': 0,
            'successful_optimizations': 0,
            'failed_optimizations': 0
        }

    def _ensure_log_file(self):
        """Ensure the feedback log file exists with proper structure."""
        if not os.path.exists(self.feedback_log):
            with open(self.feedback_log, 'w') as f:
                json.dump({
                    'metadata': {
                        'created_at': datetime.now().isoformat(),
                        'version': '1.0'
                    },
                    'feedback': []
                }, f, indent=2)

    async def tool_feedback(self, tool_name: str,
                          input_data: Dict[str, Any],
                          output_data: Dict[str, Any]) -> None:
        """
        Process and store tool feedback asynchronously.
        
        Args:
            tool_name: Name of the tool providing feedback
            input_data: Input data that led to the output
            output_data: Output data and results
        """
        if not self.enabled:
            return
            
        try:
            # Prepare feedback entry
            entry = {
                'timestamp': datetime.now().isoformat(),
                'tool_name': tool_name,
                'input_data': input_data,
                'output_data': output_data,
                'metadata': {
                    'process_time': time.time(),
                    'success': 'error' not in output_data
                }
            }
            
            # Store feedback
            await self._store_feedback(entry)
            
            # Process feedback through Seal Tools
            await self._process_seal_feedback(entry)
            
            # Update metrics
            self.metrics['total_feedback'] += 1
            
            # Check if optimization is needed
            await self._check_optimization_needed()
            
        except Exception as e:
            error_msg = f"Error processing tool feedback: {str(e)}"
            _LOGGER.error(error_msg)
            await self.logger.async_log_error(
                component="SealToolsIntegration",
                action="tool_feedback",
                error=str(e)
            )

    async def _store_feedback(self, entry: Dict[str, Any]) -> None:
        """Store feedback entry in the log file."""
        try:
            async with asyncio.Lock():
                with open(self.feedback_log, 'r') as f:
                    data = json.load(f)
                
                data['feedback'].append(entry)
                
                with open(self.feedback_log, 'w') as f:
                    json.dump(data, f, indent=2)
                    
        except Exception as e:
            _LOGGER.error(f"Error storing feedback: {str(e)}")
            raise

    async def _process_seal_feedback(self, entry: Dict[str, Any]) -> None:
        """Process feedback through Seal Tools framework."""
        try:
            # Convert entry to Seal Tools format
            seal_feedback = self.feedback_handler.format_feedback(entry)
            
            # Send feedback to Seal Tools
            await asyncio.to_thread(
                self.seal_client.send_feedback,
                seal_feedback
            )
            
        except Exception as e:
            _LOGGER.error(f"Error processing Seal feedback: {str(e)}")
            raise

    async def _check_optimization_needed(self) -> None:
        """Check if optimization should be performed based on collected feedback."""
        now = time.time()
        
        if (self.last_optimization and
            now - self.last_optimization < self.optimization_interval):
            return
            
        try:
            # Get recent feedback
            feedback_data = await self._get_recent_feedback()
            
            if len(feedback_data) >= self.min_feedback_count:
                await self._perform_optimization(feedback_data)
                self.last_optimization = now
                
        except Exception as e:
            _LOGGER.error(f"Error checking optimization: {str(e)}")

    async def _get_recent_feedback(self) -> List[Dict[str, Any]]:
        """Get recent feedback entries for optimization."""
        try:
            with open(self.feedback_log, 'r') as f:
                data = json.load(f)
            return data['feedback'][-self.min_feedback_count:]
        except Exception as e:
            _LOGGER.error(f"Error getting recent feedback: {str(e)}")
            return []

    async def _perform_optimization(self, feedback_data: List[Dict[str, Any]]) -> None:
        """Perform optimization using collected feedback."""
        try:
            # Prepare optimization data
            optimization_input = self.optimizer.prepare_optimization_input(feedback_data)
            
            # Run optimization
            optimization_result = await asyncio.to_thread(
                self.optimizer.optimize,
                optimization_input
            )
            
            # Apply optimizations
            if optimization_result.get('success'):
                await self._apply_optimizations(optimization_result['optimizations'])
                self.metrics['successful_optimizations'] += 1
            else:
                self.metrics['failed_optimizations'] += 1
                
            # Log optimization results
            await self.logger.async_log_interaction(
                component="SealToolsIntegration",
                action="optimization",
                input_data={"feedback_count": len(feedback_data)},
                output_data=optimization_result
            )
            
        except Exception as e:
            _LOGGER.error(f"Error performing optimization: {str(e)}")
            self.metrics['failed_optimizations'] += 1
            raise

    async def _apply_optimizations(self, optimizations: List[Dict[str, Any]]) -> None:
        """Apply optimizations to the system."""
        for opt in optimizations:
            try:
                # Apply each optimization through Seal Tools
                await asyncio.to_thread(
                    self.seal_client.apply_optimization,
                    opt
                )
                
                # Log applied optimization
                await self.logger.async_log_interaction(
                    component="SealToolsIntegration",
                    action="apply_optimization",
                    input_data=opt,
                    output_data={"status": "success"}
                )
                
            except Exception as e:
                _LOGGER.error(f"Error applying optimization: {str(e)}")
                continue

    async def get_metrics(self) -> Dict[str, Any]:
        """Get current performance metrics."""
        return {
            **self.metrics,
            'last_optimization': self.last_optimization,
            'enabled': self.enabled
        }

    async def get_optimization_status(self) -> Dict[str, Any]:
        """Get current optimization status and statistics."""
        try:
            with open(self.feedback_log, 'r') as f:
                data = json.load(f)
                
            return {
                'total_feedback_count': len(data['feedback']),
                'last_optimization': self.last_optimization,
                'optimization_interval': self.optimization_interval,
                'min_feedback_count': self.min_feedback_count,
                'metrics': self.metrics
            }
        except Exception as e:
            _LOGGER.error(f"Error getting optimization status: {str(e)}")
            return {} 