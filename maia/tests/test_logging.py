import os
import json
import time
import asyncio
from pathlib import Path
from ..core.logging import get_logger

async def test_logging_levels():
    """Test different logging levels and verify output."""
    logger = get_logger("test.levels")
    
    print("Testing logging levels...")
    
    # Test each level
    logger.debug("Debug message with details", extra_info="debug_data")
    logger.info("Info message about state", state="running")
    logger.warning("Warning about resource", resource="memory", usage=85)
    logger.error("Error in operation", operation="data_fetch", error_code=500)
    logger.critical("Critical system error", component="database", status="offline")
    
    # Verify log files exist
    json_log = Path("/data/logs/maia.json")
    debug_log = Path("/data/logs/maia.debug.log")
    
    assert json_log.exists(), "JSON log file not created"
    assert debug_log.exists(), "Debug log file not created"
    
    # Read and verify JSON log format
    with open(json_log) as f:
        for line in f:
            entry = json.loads(line)
            assert "timestamp" in entry
            assert "level" in entry
            assert "message" in entry
            print(f"Verified log entry: {entry['level']} - {entry['message']}")

@logger.performance("test_operation")
async def sample_operation():
    """Test operation for performance logging."""
    await asyncio.sleep(0.5)  # Simulate work
    return "operation complete"

async def test_performance_logging():
    """Test performance logging decorator."""
    print("\nTesting performance logging...")
    result = await sample_operation()
    print(f"Operation result: {result}")
    
    # Verify performance metrics in log
    with open("/data/logs/maia.json") as f:
        logs = f.readlines()
        performance_logs = [json.loads(log) for log in logs 
                          if "Performance: test_operation" in json.loads(log)["message"]]
        assert performance_logs, "Performance log entry not found"
        print(f"Performance metrics: {performance_logs[-1]}")

async def test_system_metrics():
    """Test system metrics collection."""
    print("\nTesting system metrics logging...")
    logger = get_logger("test.metrics")
    
    # Force system metrics collection with debug
    logger.debug("Collecting system metrics")
    
    # Verify metrics in log
    with open("/data/logs/maia.json") as f:
        logs = f.readlines()
        metric_logs = [json.loads(log) for log in logs 
                      if "system_metrics" in json.loads(log).get("context", {})]
        assert metric_logs, "System metrics not found in logs"
        metrics = metric_logs[-1]["context"]["system_metrics"]
        print("System metrics collected:")
        print(f"Memory: {metrics['memory_usage']}")
        print(f"CPU: {metrics['cpu_percent']}%")
        print(f"Threads: {metrics['thread_count']}")

async def test_request_tracking():
    """Test request ID tracking."""
    print("\nTesting request tracking...")
    logger = get_logger("test.requests")
    
    # Simulate request handling
    request_id = "test-request-123"
    logger.set_request_id(request_id)
    logger.info("Processing request", endpoint="/api/test")
    
    # Verify request ID in logs
    with open("/data/logs/maia.json") as f:
        logs = f.readlines()
        request_logs = [json.loads(log) for log in logs 
                       if request_id in json.loads(log).get("request_id", "")]
        assert request_logs, "Request tracking log not found"
        print(f"Request tracking verified: {request_logs[-1]}")

async def main():
    """Run all logging tests."""
    os.environ["LOG_LEVEL"] = "DEBUG"  # Enable all logging for tests
    
    print("Starting logging system tests...")
    
    try:
        await test_logging_levels()
        await test_performance_logging()
        await test_system_metrics()
        await test_request_tracking()
        print("\nAll logging tests completed successfully!")
    except Exception as e:
        print(f"Test failed: {str(e)}")
        raise

if __name__ == "__main__":
    asyncio.run(main()) 