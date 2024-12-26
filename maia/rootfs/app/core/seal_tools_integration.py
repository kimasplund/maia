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

class SealToolsConfig:
    """Configuration for Seal Tools integration."""
    def __init__(self, config: Dict[str, Any]):
        self.api_key = config.get('api_key', os.getenv("SEAL_API_KEY"))
        self.endpoint = config.get('endpoint', "https://api.seal.ai")
        self.model = config.get('model', "seal-1")
        self.max_retries = config.get('max_retries', 3)
        self.timeout = config.get('timeout', 30)
        self.feedback_batch_size = config.get('feedback_batch_size', 10)
        self.optimization_interval = config.get('optimization_interval', 3600)
        self.enable_async_feedback = config.get('enable_async_feedback', True)
        self.debug_mode = config.get('debug_mode', False)

class SealToolsIntegration:
    """Integration with Seal Tools for tool optimization."""
    
    def __init__(self, config: Dict[str, Any]):
        """Initialize Seal Tools integration."""
        self.config = SealToolsConfig(config)
        self.client = SealClient(
            api_key=self.config.api_key,
            endpoint=self.config.endpoint
        )
        self.optimizer = SealOptimizer(
            client=self.client,
            model=self.config.model
        )
        self.feedback_queue: List[Dict[str, Any]] = []
        self.last_optimization = time.time()
        self.logger = AsyncLogger(__name__)
        
    async def optimize_tool(self, tool_id: str, feedback: List[Dict[str, Any]]) -> Dict[str, Any]:
        """Optimize a tool based on feedback."""
        try:
            # Prepare feedback data
            feedback_data = SealFeedback(
                tool_id=tool_id,
                feedback=feedback,
                timestamp=datetime.now().isoformat()
            )
            
            # Submit feedback for optimization
            result = await self.optimizer.optimize(feedback_data)
            
            # Log optimization result
            await self.logger.info(
                f"Tool optimization completed",
                extra={
                    "tool_id": tool_id,
                    "feedback_count": len(feedback),
                    "optimization_result": result
                }
            )
            
            return result
            
        except Exception as e:
            await self.logger.error(
                f"Tool optimization failed: {str(e)}",
                extra={"tool_id": tool_id}
            )
            return {
                "error": str(e),
                "timestamp": datetime.now().isoformat()
            }
            
    async def submit_feedback(self, feedback: Dict[str, Any]) -> None:
        """Submit feedback for tool optimization."""
        try:
            # Add feedback to queue
            self.feedback_queue.append(feedback)
            
            # Process feedback queue if batch size reached
            if len(self.feedback_queue) >= self.config.feedback_batch_size:
                await self._process_feedback_queue()
                
            # Check if optimization interval reached
            current_time = time.time()
            if (current_time - self.last_optimization) >= self.config.optimization_interval:
                await self._run_optimization()
                self.last_optimization = current_time
                
        except Exception as e:
            await self.logger.error(
                f"Failed to submit feedback: {str(e)}",
                extra={"feedback": feedback}
            )
            
    async def _process_feedback_queue(self) -> None:
        """Process queued feedback."""
        if not self.feedback_queue:
            return
            
        try:
            # Group feedback by tool
            feedback_by_tool: Dict[str, List[Dict[str, Any]]] = {}
            for feedback in self.feedback_queue:
                tool_id = feedback.get("tool_id")
                if tool_id:
                    if tool_id not in feedback_by_tool:
                        feedback_by_tool[tool_id] = []
                    feedback_by_tool[tool_id].append(feedback)
                    
            # Process each tool's feedback
            for tool_id, tool_feedback in feedback_by_tool.items():
                await self.optimize_tool(tool_id, tool_feedback)
                
            # Clear processed feedback
            self.feedback_queue.clear()
            
        except Exception as e:
            await self.logger.error(
                f"Failed to process feedback queue: {str(e)}"
            )
            
    async def _run_optimization(self) -> None:
        """Run optimization for all tools."""
        try:
            # Get all tools
            tools = await self.client.list_tools()
            
            # Optimize each tool
            for tool in tools:
                tool_id = tool.get("id")
                if tool_id:
                    # Get tool feedback
                    feedback = await self.client.get_tool_feedback(tool_id)
                    if feedback:
                        await self.optimize_tool(tool_id, feedback)
                        
        except Exception as e:
            await self.logger.error(
                f"Failed to run optimization: {str(e)}"
            )
            
    def cleanup(self):
        """Clean up resources."""
        # Process any remaining feedback
        if self.feedback_queue:
            asyncio.create_task(self._process_feedback_queue())
            
        # Clear feedback queue
        self.feedback_queue.clear() 