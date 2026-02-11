"""
Data Mapper: OpenClaw Sessions → AgentWatch Telemetry

Converts OpenClaw session data to AgentWatch API schema.
Pure Python mapping — no LLM analysis.
"""

from datetime import datetime
from typing import Dict, Any, List
import uuid
from .openclaw_client import SessionTelemetry


class TelemetryEvent:
    """Represents a single AgentWatch telemetry event."""
    
    def __init__(self, 
                 agent_name: str,
                 agent_id: str,
                 event_type: str,  # "execution", "completion", "error"
                 trace_id: str,
                 session_id: str,
                 input_tokens: int = 0,
                 output_tokens: int = 0,
                 model: str = "unknown",
                 status: str = "running",
                 metadata: Dict[str, Any] = None):
        self.agent_name = agent_name
        self.agent_id = agent_id
        self.event_type = event_type
        self.trace_id = trace_id
        self.session_id = session_id
        self.input_tokens = input_tokens
        self.output_tokens = output_tokens
        self.model = model
        self.status = status
        self.metadata = metadata or {}
        self.timestamp = datetime.utcnow().isoformat()
    
    def to_dict(self) -> Dict[str, Any]:
        """Serialize for AgentWatch API."""
        return {
            "agent_name": self.agent_name,
            "agent_id": self.agent_id,
            "event_type": self.event_type,
            "trace_id": self.trace_id,
            "session_id": self.session_id,
            "input_tokens": self.input_tokens,
            "output_tokens": self.output_tokens,
            "model": self.model,
            "status": self.status,
            "metadata": self.metadata,
            "timestamp": self.timestamp,
        }


class DataMapper:
    """Maps OpenClaw sessions to AgentWatch telemetry."""
    
    # Filter out internal/monitoring sessions
    SKIP_KINDS = {"cron"}  # Don't track cron jobs (they're internal monitoring)
    
    def __init__(self, min_tokens: int = 10):
        """
        Args:
            min_tokens: Skip sessions with fewer tokens (reduces noise)
        """
        self.min_tokens = min_tokens
        self._session_traces = {}  # Cache: session_id → trace_id (for correlation)
    
    def should_ingest(self, telemetry: SessionTelemetry) -> bool:
        """Decide if this session should generate telemetry (code-based filtering)."""
        # Skip internal kinds
        if telemetry.kind in self.SKIP_KINDS:
            return False
        
        # Skip low-signal sessions
        if telemetry.total_tokens < self.min_tokens:
            return False
        
        return True
    
    def map_session(self, telemetry: SessionTelemetry) -> List[TelemetryEvent]:
        """
        Convert a session to telemetry events.
        
        Returns:
            List of TelemetryEvent objects (usually 1, but can be multiple
            if session had major state changes)
        """
        if not self.should_ingest(telemetry):
            return []
        
        # Derive or reuse trace ID (for correlation across multiple calls)
        trace_id = self._session_traces.get(
            telemetry.session_id,
            str(uuid.uuid4())
        )
        self._session_traces[telemetry.session_id] = trace_id
        
        # Create event
        event = TelemetryEvent(
            agent_name=self._infer_agent_name(telemetry),
            agent_id=telemetry.agent_id,
            event_type=self._infer_event_type(telemetry),
            trace_id=trace_id,
            session_id=telemetry.session_id,
            input_tokens=self._estimate_input_tokens(telemetry),
            output_tokens=self._estimate_output_tokens(telemetry),
            model=telemetry.model,
            status=telemetry.status,
            metadata={
                "kind": telemetry.kind,
                "label": telemetry.label,
                "channel": telemetry.channel,
                "context_used_pct": int((telemetry.context_tokens / 120000) * 100) if telemetry.context_tokens > 0 else 0,
            }
        )
        
        return [event]
    
    @staticmethod
    def _infer_agent_name(telemetry: SessionTelemetry) -> str:
        """Extract readable agent name from telemetry."""
        if telemetry.label:
            return telemetry.label.replace("gh-taskmaster:", "").split("--")[0]
        return telemetry.agent_id or "unknown-agent"
    
    @staticmethod
    def _infer_event_type(telemetry: SessionTelemetry) -> str:
        """Infer event type from status."""
        if telemetry.status == "error":
            return "error"
        elif telemetry.status == "completed":
            return "completion"
        return "execution"
    
    @staticmethod
    def _estimate_input_tokens(telemetry: SessionTelemetry) -> int:
        """Rough estimate of input tokens (assume 60% input, 40% output)."""
        return int(telemetry.total_tokens * 0.6)
    
    @staticmethod
    def _estimate_output_tokens(telemetry: SessionTelemetry) -> int:
        """Rough estimate of output tokens."""
        return int(telemetry.total_tokens * 0.4)
    
    def clear_stale_traces(self, max_age_hours: int = 24):
        """
        Clear cached trace mappings older than X hours.
        Prevents memory leak from long-running syncer.
        """
        # TODO: Implement with timestamps if needed
        pass
