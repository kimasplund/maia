"""
GPU monitoring and optimization for MAIA nodes.
Handles GPU resource tracking, optimization, and CUDA settings.
"""
from typing import Dict, List, Optional, Any
import logging
import asyncio
import nvidia_smi
import torch
import torch.cuda
import os
from dataclasses import dataclass
from datetime import datetime

_LOGGER = logging.getLogger(__name__)

@dataclass
class GPUStats:
    """GPU statistics."""
    index: int
    name: str
    uuid: str
    temperature: int  # Celsius
    power_usage: float  # Watts
    power_limit: float  # Watts
    memory_used: int  # MB
    memory_total: int  # MB
    utilization: int  # Percent
    compute_mode: str
    clock_speeds: Dict[str, int]  # MHz
    processes: List[Dict[str, Any]]

class GPUMonitor:
    """GPU monitoring and optimization."""
    
    def __init__(self):
        """Initialize GPU monitor."""
        self.nvidia_smi = nvidia_smi
        self.update_interval = 1.0  # seconds
        self.running = False
        self.stats: Dict[int, GPUStats] = {}
        self._optimize_cuda()
        
    def _optimize_cuda(self):
        """Apply CUDA optimizations."""
        try:
            if not torch.cuda.is_available():
                return
                
            # Set CUDA device flags
            torch.backends.cuda.matmul.allow_tf32 = True  # Allow TF32 for better performance
            torch.backends.cudnn.benchmark = True  # Enable cudnn autotuner
            torch.backends.cudnn.enabled = True
            torch.backends.cudnn.deterministic = False  # Better performance but non-deterministic
            
            # Set environment variables
            os.environ["CUDA_LAUNCH_BLOCKING"] = "0"
            os.environ["CUDA_CACHE_PATH"] = "/tmp/cuda_cache"
            os.environ["CUDA_AUTO_TUNE"] = "1"
            
            # Initialize CUDA cache
            torch.cuda.init()
            
            # Warm up CUDA
            device = torch.device("cuda")
            torch.zeros(1).to(device)
            
            _LOGGER.info("CUDA optimizations applied successfully")
            
        except Exception as e:
            _LOGGER.error(f"Failed to apply CUDA optimizations: {str(e)}")
            
    async def start(self):
        """Start GPU monitoring."""
        try:
            self.nvidia_smi.nvmlInit()
            self.running = True
            
            # Start monitoring loop
            asyncio.create_task(self._monitor_loop())
            _LOGGER.info("GPU monitoring started")
            
        except Exception as e:
            _LOGGER.error(f"Failed to start GPU monitoring: {str(e)}")
            raise
            
    async def stop(self):
        """Stop GPU monitoring."""
        try:
            self.running = False
            self.nvidia_smi.nvmlShutdown()
            _LOGGER.info("GPU monitoring stopped")
            
        except Exception as e:
            _LOGGER.error(f"Failed to stop GPU monitoring: {str(e)}")
            
    async def _monitor_loop(self):
        """GPU monitoring loop."""
        while self.running:
            try:
                await self._update_stats()
                await self._optimize_gpu()
                await asyncio.sleep(self.update_interval)
                
            except Exception as e:
                _LOGGER.error(f"Error in GPU monitoring loop: {str(e)}")
                await asyncio.sleep(self.update_interval)
                
    async def _update_stats(self):
        """Update GPU statistics."""
        try:
            device_count = self.nvidia_smi.nvmlDeviceGetCount()
            
            for i in range(device_count):
                handle = self.nvidia_smi.nvmlDeviceGetHandleByIndex(i)
                
                # Get basic info
                info = self.nvidia_smi.nvmlDeviceGetMemoryInfo(handle)
                temp = self.nvidia_smi.nvmlDeviceGetTemperature(
                    handle,
                    self.nvidia_smi.NVML_TEMPERATURE_GPU
                )
                power = self.nvidia_smi.nvmlDeviceGetPowerUsage(handle) / 1000.0
                power_limit = self.nvidia_smi.nvmlDeviceGetEnforcedPowerLimit(handle) / 1000.0
                util = self.nvidia_smi.nvmlDeviceGetUtilizationRates(handle)
                
                # Get clock speeds
                graphics_clock = self.nvidia_smi.nvmlDeviceGetClockInfo(
                    handle,
                    self.nvidia_smi.NVML_CLOCK_GRAPHICS
                )
                mem_clock = self.nvidia_smi.nvmlDeviceGetClockInfo(
                    handle,
                    self.nvidia_smi.NVML_CLOCK_MEM
                )
                sm_clock = self.nvidia_smi.nvmlDeviceGetClockInfo(
                    handle,
                    self.nvidia_smi.NVML_CLOCK_SM
                )
                
                # Get process info
                processes = []
                for proc in self.nvidia_smi.nvmlDeviceGetComputeRunningProcesses(handle):
                    try:
                        process_name = self.nvidia_smi.nvmlSystemGetProcessName(proc.pid)
                        processes.append({
                            "pid": proc.pid,
                            "name": process_name.decode() if process_name else "unknown",
                            "memory": proc.usedGpuMemory / 1024 / 1024  # Convert to MB
                        })
                    except:
                        continue
                        
                # Update stats
                self.stats[i] = GPUStats(
                    index=i,
                    name=self.nvidia_smi.nvmlDeviceGetName(handle).decode(),
                    uuid=self.nvidia_smi.nvmlDeviceGetUUID(handle).decode(),
                    temperature=temp,
                    power_usage=power,
                    power_limit=power_limit,
                    memory_used=info.used / 1024 / 1024,  # Convert to MB
                    memory_total=info.total / 1024 / 1024,
                    utilization=util.gpu,
                    compute_mode=self.nvidia_smi.nvmlDeviceGetComputeMode(handle),
                    clock_speeds={
                        "graphics": graphics_clock,
                        "memory": mem_clock,
                        "sm": sm_clock
                    },
                    processes=processes
                )
                
        except Exception as e:
            _LOGGER.error(f"Failed to update GPU stats: {str(e)}")
            
    async def _optimize_gpu(self):
        """Apply GPU optimizations based on current state."""
        try:
            device_count = self.nvidia_smi.nvmlDeviceGetCount()
            
            for i in range(device_count):
                handle = self.nvidia_smi.nvmlDeviceGetHandleByIndex(i)
                stats = self.stats.get(i)
                
                if not stats:
                    continue
                    
                # Adjust power limit based on utilization
                if stats.utilization < 50 and stats.power_usage > stats.power_limit * 0.8:
                    new_limit = int(stats.power_limit * 0.9 * 1000)  # Convert to mW
                    try:
                        self.nvidia_smi.nvmlDeviceSetPowerLimit(handle, new_limit)
                    except:
                        pass
                        
                # Adjust GPU clocks based on workload
                if stats.utilization > 90:
                    try:
                        # Set max clocks for heavy workload
                        self.nvidia_smi.nvmlDeviceSetApplicationsClocks(
                            handle,
                            self.nvidia_smi.NVML_CLOCK_MEM,
                            max(self._get_supported_mem_clocks(handle))
                        )
                    except:
                        pass
                elif stats.utilization < 20:
                    try:
                        # Reset clocks for light workload
                        self.nvidia_smi.nvmlDeviceResetApplicationsClocks(handle)
                    except:
                        pass
                        
                # Set compute mode for optimal performance
                if stats.compute_mode != self.nvidia_smi.NVML_COMPUTEMODE_DEFAULT:
                    try:
                        self.nvidia_smi.nvmlDeviceSetComputeMode(
                            handle,
                            self.nvidia_smi.NVML_COMPUTEMODE_DEFAULT
                        )
                    except:
                        pass
                        
        except Exception as e:
            _LOGGER.error(f"Failed to optimize GPU: {str(e)}")
            
    def _get_supported_mem_clocks(self, handle) -> List[int]:
        """Get supported memory clock speeds."""
        try:
            return self.nvidia_smi.nvmlDeviceGetSupportedMemoryClocks(handle)
        except:
            return []
            
    async def get_stats(self) -> Dict[str, Any]:
        """Get current GPU statistics."""
        try:
            return {
                str(idx): {
                    "name": stats.name,
                    "uuid": stats.uuid,
                    "temperature": stats.temperature,
                    "power": {
                        "usage": stats.power_usage,
                        "limit": stats.power_limit
                    },
                    "memory": {
                        "used": stats.memory_used,
                        "total": stats.memory_total,
                        "percent": (stats.memory_used / stats.memory_total) * 100
                    },
                    "utilization": stats.utilization,
                    "clocks": stats.clock_speeds,
                    "processes": stats.processes
                }
                for idx, stats in self.stats.items()
            }
            
        except Exception as e:
            _LOGGER.error(f"Failed to get GPU stats: {str(e)}")
            return {} 