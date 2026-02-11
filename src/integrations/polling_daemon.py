"""
OpenClaw → AgentWatch Polling Daemon

Continuously polls OpenClaw sessions, maps to telemetry, pushes to AgentWatch.
Designed for minimal overhead (code-only filtering, no LLM during polling).
"""

import time
import logging
import sys
from datetime import datetime, timedelta
from typing import Optional
import httpx
from .openclaw_client import OpenClawClient, OpenClawError
from .data_mapper import DataMapper, TelemetryEvent


logger = logging.getLogger(__name__)


class PollingDaemon:
    """
    Non-blocking daemon that:
    1. Polls OpenClaw sessions_list every N seconds
    2. Filters with code-based logic
    3. Maps to AgentWatch telemetry
    4. Pushes to AgentWatch API
    5. Tracks state (prevent duplicate ingestion)
    """
    
    def __init__(self,
                 openclaw_url: str = "http://127.0.0.1:18789",
                 agentwatch_url: str = "http://localhost:8765",
                 poll_interval_s: int = 30,
                 batch_size: int = 50,
                 max_errors: int = 10):
        """
        Args:
            openclaw_url: OpenClaw gateway URL
            agentwatch_url: AgentWatch API URL
            poll_interval_s: Seconds between polls
            batch_size: Max sessions to fetch per poll
            max_errors: Stop after N consecutive errors
        """
        self.openclaw_url = openclaw_url
        self.agentwatch_url = agentwatch_url.rstrip("/")
        self.poll_interval_s = poll_interval_s
        self.batch_size = batch_size
        self.max_errors = max_errors
        
        self.openclaw = OpenClawClient(api_url=openclaw_url)
        self.mapper = DataMapper()
        self.client = httpx.Client(timeout=10)
        
        self.last_poll_time = None
        self.consecutive_errors = 0
        self.total_events_ingested = 0
        self.session_seen = set()  # Track seen sessions to avoid duplicates
    
    def run(self, run_forever: bool = True):
        """
        Start the polling loop.
        
        Args:
            run_forever: If True, run indefinitely. If False, run once.
        """
        logger.info(f"Starting OpenClaw→AgentWatch polling daemon")
        logger.info(f"  Poll interval: {self.poll_interval_s}s")
        logger.info(f"  OpenClaw URL: {self.openclaw_url}")
        logger.info(f"  AgentWatch URL: {self.agentwatch_url}")
        
        iteration = 0
        
        while True:
            try:
                iteration += 1
                self._poll_once(iteration)
                self.consecutive_errors = 0
                
                if not run_forever:
                    break
                
                time.sleep(self.poll_interval_s)
            
            except KeyboardInterrupt:
                logger.info("Shutdown requested (Ctrl+C)")
                break
            except Exception as e:
                self.consecutive_errors += 1
                logger.error(f"Poll error (attempt {self.consecutive_errors}/{self.max_errors}): {e}")
                
                if self.consecutive_errors >= self.max_errors:
                    logger.critical(f"Max errors reached. Stopping.")
                    break
                
                time.sleep(self.poll_interval_s)
        
        self.cleanup()
    
    def _poll_once(self, iteration: int):
        """
        Single polling iteration:
        1. Fetch sessions from OpenClaw
        2. Filter/map to telemetry
        3. Push to AgentWatch
        4. Update state
        """
        start_time = time.time()
        
        # Fetch sessions (kinds: main, subagent, group — skip cron)
        try:
            sessions = self.openclaw.get_sessions(
                kinds=["main", "subagent", "group"],
                limit=self.batch_size,
                active_minutes=30  # Only active in last 30 min
            )
        except OpenClawError as e:
            # Log but don't fail — might be CLI not found, HTTP may fail
            logger.warning(f"Could not fetch sessions: {e}")
            elapsed = time.time() - start_time
            logger.debug(f"Poll #{iteration}: Failed to fetch sessions ({elapsed:.2f}s)")
            return
        
        # Map to telemetry events
        events = []
        for session in sessions:
            session_id = session.get("sessionId")
            
            # Skip if we've already ingested this session recently
            if session_id in self.session_seen:
                continue
            
            telemetry = self.openclaw.extract_telemetry(session)
            session_events = self.mapper.map_session(telemetry)
            events.extend(session_events)
            
            if session_events:
                self.session_seen.add(session_id)
        
        # Push to AgentWatch (batch)
        if events:
            self._ingest_batch(events)
        
        elapsed = time.time() - start_time
        logger.debug(
            f"Poll #{iteration}: {len(sessions)} sessions → "
            f"{len(events)} events ({elapsed:.2f}s)"
        )
    
    def _ingest_batch(self, events: list):
        """
        Push telemetry batch to AgentWatch API.
        
        Posts each event as a separate trace (since AgentWatch schema uses traces as primary entity).
        """
        count = 0
        for event in events:
            try:
                # Map event to trace schema
                payload = {
                    "agent_id": event.agent_id,
                    "environment": "production",
                    "task_type": event.metadata.get("kind", "unknown"),
                    "input_summary": event.agent_name,
                    "attributes": {
                        "session_id": event.session_id,
                        "trace_id": event.trace_id,
                        "label": event.metadata.get("label"),
                        "channel": event.metadata.get("channel"),
                    }
                }
                
                # Create trace
                resp = self.client.post(
                    f"{self.agentwatch_url}/api/traces",
                    json=payload
                )
                
                if resp.status_code == 200:
                    trace_data = resp.json()
                    trace_id = trace_data.get("id")
                    
                    # Now add cost/token data as an event
                    cost_payload = {
                        "trace_id": trace_id,
                        "input_tokens": event.input_tokens,
                        "output_tokens": event.output_tokens,
                        "model": event.model,
                        "amount": self._estimate_cost(event.model, event.input_tokens, event.output_tokens),
                        "currency": "USD"
                    }
                    
                    cost_resp = self.client.post(
                        f"{self.agentwatch_url}/api/traces/{trace_id}/events",
                        json=cost_payload
                    )
                    
                    count += 1
                else:
                    logger.warning(f"Trace creation returned {resp.status_code}: {resp.text}")
            
            except httpx.HTTPError as e:
                logger.error(f"Ingest failed for event {event.agent_name}: {e}")
        
        self.total_events_ingested += count
        if count > 0:
            logger.info(f"✓ Ingested {count} events (total: {self.total_events_ingested})")
    
    @staticmethod
    def _estimate_cost(model: str, input_tokens: int, output_tokens: int) -> float:
        """Estimate cost in USD based on model and tokens."""
        # Simplified pricing (matches AgentWatch model_pricing)
        pricing = {
            "claude-haiku-4-5": {"input": 0.00025, "output": 0.00125},
            "claude-3-sonnet": {"input": 0.003, "output": 0.015},
            "claude-3-opus": {"input": 0.015, "output": 0.075},
            "gpt-4o": {"input": 0.005, "output": 0.015},
        }
        
        model_price = pricing.get(model, {"input": 0.0001, "output": 0.0001})
        cost = (input_tokens * model_price["input"] + output_tokens * model_price["output"]) / 1000
        return round(cost, 6)
    
    def cleanup(self):
        """Graceful shutdown."""
        logger.info("Cleaning up...")
        self.openclaw.close()
        self.client.close()
        logger.info(f"Daemon stopped. Total events ingested: {self.total_events_ingested}")


def main():
    """CLI entry point."""
    import argparse
    
    parser = argparse.ArgumentParser(
        description="OpenClaw → AgentWatch polling daemon"
    )
    parser.add_argument(
        "--openclaw-url",
        default="http://127.0.0.1:18789",
        help="OpenClaw gateway URL"
    )
    parser.add_argument(
        "--agentwatch-url",
        default="http://localhost:8765",
        help="AgentWatch API URL"
    )
    parser.add_argument(
        "--poll-interval",
        type=int,
        default=30,
        help="Poll interval in seconds"
    )
    parser.add_argument(
        "--log-level",
        default="INFO",
        choices=["DEBUG", "INFO", "WARNING", "ERROR"],
        help="Logging level"
    )
    parser.add_argument(
        "--once",
        action="store_true",
        help="Run once and exit (for testing)"
    )
    
    args = parser.parse_args()
    
    # Configure logging
    logging.basicConfig(
        level=getattr(logging, args.log_level),
        format="%(asctime)s [%(levelname)s] %(message)s"
    )
    
    # Run daemon
    daemon = PollingDaemon(
        openclaw_url=args.openclaw_url,
        agentwatch_url=args.agentwatch_url,
        poll_interval_s=args.poll_interval
    )
    daemon.run(run_forever=not args.once)


if __name__ == "__main__":
    main()
