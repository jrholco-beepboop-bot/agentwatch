#!/usr/bin/env python3
"""
Quick validation test for the OpenClaw→AgentWatch syncer.

Run this to verify everything is wired up before starting the daemon.
"""

import sys
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


def test_openclaw_connectivity():
    """Check if OpenClaw gateway is reachable."""
    from src.integrations.openclaw_client import OpenClawClient, OpenClawError
    
    logger.info("Testing OpenClaw connectivity...")
    client = OpenClawClient(api_url="http://127.0.0.1:18789")
    
    try:
        sessions = client.get_sessions(limit=5)
        logger.info(f"✓ OpenClaw reachable. Found {len(sessions)} sessions.")
        
        if sessions:
            logger.info(f"  Sample session: {sessions[0].get('key')} ({sessions[0].get('kind')})")
        
        client.close()
        return True
    except OpenClawError as e:
        logger.error(f"✗ OpenClaw failed: {e}")
        return False


def test_data_mapper():
    """Check if data mapper works."""
    from src.integrations.openclaw_client import OpenClawClient, SessionTelemetry
    from src.integrations.data_mapper import DataMapper
    
    logger.info("\nTesting DataMapper...")
    client = OpenClawClient(api_url="http://127.0.0.1:18789")
    mapper = DataMapper()
    
    try:
        sessions = client.get_sessions(limit=5)
        
        if not sessions:
            logger.warning("No sessions to map. (This is OK if OpenClaw is idle)")
            return True
        
        # Try mapping first session
        session = sessions[0]
        telemetry = client.extract_telemetry(session)
        events = mapper.map_session(telemetry)
        
        if events:
            logger.info(f"✓ Mapper works. Created {len(events)} event(s) from session.")
            logger.info(f"  Event: {events[0].agent_name} ({events[0].model})")
        else:
            logger.info(f"✓ Mapper filtered out session (normal for cron jobs).")
        
        client.close()
        return True
    except Exception as e:
        logger.error(f"✗ Mapper failed: {e}")
        return False


def test_agentwatch_connectivity():
    """Check if AgentWatch API is reachable."""
    import httpx
    
    logger.info("\nTesting AgentWatch connectivity...")
    
    try:
        resp = httpx.get("http://localhost:8765/docs", timeout=5)
        logger.info(f"✓ AgentWatch reachable (HTTP {resp.status_code}).")
        return True
    except httpx.ConnectError:
        logger.error("✗ AgentWatch not reachable at http://localhost:8765")
        logger.error("  Run: python run.py")
        return False
    except Exception as e:
        logger.error(f"✗ AgentWatch test failed: {e}")
        return False


def test_agentwatch_ingest():
    """Try posting a test event to AgentWatch."""
    import httpx
    
    logger.info("\nTesting AgentWatch ingest...")
    
    try:
        payload = {
            "events": [
                {
                    "agent_name": "test-agent",
                    "agent_id": "haiku",
                    "event_type": "execution",
                    "trace_id": "test-trace-001",
                    "session_id": "test-session-001",
                    "input_tokens": 100,
                    "output_tokens": 200,
                    "model": "claude-haiku-4-5",
                    "status": "completed",
                    "metadata": {"test": True},
                    "timestamp": "2026-02-10T20:30:00Z"
                }
            ]
        }
        
        resp = httpx.post(
            "http://localhost:8765/api/events/bulk",
            json=payload,
            timeout=5
        )
        
        if resp.status_code == 200:
            logger.info(f"✓ Ingest works (HTTP {resp.status_code}).")
            return True
        else:
            logger.warning(f"⚠ Ingest returned HTTP {resp.status_code}")
            logger.warning(f"  Response: {resp.text}")
            return False
    except httpx.ConnectError:
        logger.error("✗ Could not reach AgentWatch API")
        return False
    except Exception as e:
        logger.error(f"✗ Ingest test failed: {e}")
        return False


def main():
    logger.info("=" * 60)
    logger.info("AgentWatch OpenClaw Syncer - Validation Test")
    logger.info("=" * 60)
    
    results = {
        "OpenClaw connectivity": test_openclaw_connectivity(),
        "DataMapper": test_data_mapper(),
        "AgentWatch connectivity": test_agentwatch_connectivity(),
        "AgentWatch ingest": test_agentwatch_ingest(),
    }
    
    logger.info("\n" + "=" * 60)
    logger.info("Test Results:")
    logger.info("=" * 60)
    
    for test_name, passed in results.items():
        status = "✓ PASS" if passed else "✗ FAIL"
        logger.info(f"{status}: {test_name}")
    
    all_passed = all(results.values())
    
    logger.info("=" * 60)
    
    if all_passed:
        logger.info("✓ All tests passed! Ready to start syncer:")
        logger.info("")
        logger.info("  python start_syncer.py")
        logger.info("")
        return 0
    else:
        logger.error("✗ Some tests failed. Fix above issues before starting.")
        return 1


if __name__ == "__main__":
    sys.exit(main())
