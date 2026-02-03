"""
AgentWatch SDK Client

Main client for sending telemetry to AgentWatch.
"""

import os
import uuid
import httpx
from datetime import datetime
from typing import Optional, Dict, Any, List
from contextlib import contextmanager
from dataclasses import dataclass, field


@dataclass
class SpanContext:
    """Context for a trace span."""
    trace_id: str
    agent_id: str
    environment: str
    user_id: Optional[str] = None
    session_id: Optional[str] = None
    task_type: Optional[str] = None
    attributes: Dict[str, Any] = field(default_factory=dict)
    events: List[Dict] = field(default_factory=list)
    costs: List[Dict] = field(default_factory=list)
    compliance_events: List[Dict] = field(default_factory=list)
    status: str = "running"
    error_message: Optional[str] = None
    input_summary: Optional[str] = None
    output_summary: Optional[str] = None


class Span:
    """A trace span representing an agent execution."""
    
    def __init__(self, context: SpanContext, client: "AgentWatch"):
        self._context = context
        self._client = client
        self._start_time = datetime.utcnow()
    
    @property
    def trace_id(self) -> str:
        return self._context.trace_id
    
    def set_attribute(self, key: str, value: Any):
        """Set a custom attribute on this span."""
        self._context.attributes[key] = value
    
    def set_status(self, status: str, error_message: Optional[str] = None):
        """Set the span status (success, error, timeout)."""
        self._context.status = status
        if error_message:
            self._context.error_message = error_message
    
    def set_input(self, summary: str):
        """Set input summary (truncated/redacted)."""
        self._context.input_summary = summary[:1000]  # Truncate
    
    def set_output(self, summary: str):
        """Set output summary (truncated/redacted)."""
        self._context.output_summary = summary[:1000]  # Truncate
    
    def log_event(
        self,
        event_type: str,
        event_name: Optional[str] = None,
        input_data: Optional[Dict] = None,
        output_data: Optional[Dict] = None,
        duration_ms: Optional[int] = None,
        status: Optional[str] = None,
        **kwargs
    ):
        """Log a generic event."""
        self._context.events.append({
            "event_type": event_type,
            "event_name": event_name,
            "input_data": input_data,
            "output_data": output_data,
            "duration_ms": duration_ms,
            "status": status,
            "attributes": kwargs
        })
    
    def log_llm_call(
        self,
        model: str,
        input_tokens: int,
        output_tokens: int,
        duration_ms: Optional[int] = None,
        status: str = "success",
        **kwargs
    ):
        """Log an LLM API call."""
        self._context.events.append({
            "event_type": "llm_call",
            "event_name": f"LLM: {model}",
            "model": model,
            "input_tokens": input_tokens,
            "output_tokens": output_tokens,
            "duration_ms": duration_ms,
            "status": status,
            "attributes": kwargs
        })
    
    def log_tool_call(
        self,
        tool_name: str,
        input_data: Optional[Dict] = None,
        output_data: Optional[Dict] = None,
        duration_ms: Optional[int] = None,
        status: str = "success"
    ):
        """Log a tool invocation."""
        self._context.events.append({
            "event_type": "tool_call",
            "event_name": f"Tool: {tool_name}",
            "input_data": input_data,
            "output_data": output_data,
            "duration_ms": duration_ms,
            "status": status
        })
    
    def log_cost(
        self,
        amount: float,
        category: str = "other",
        currency: str = "USD",
        **kwargs
    ):
        """Log a cost entry."""
        self._context.costs.append({
            "amount": amount,
            "category": category,
            "currency": currency,
            **kwargs
        })
    
    def log_compliance_event(
        self,
        event_type: str,
        action: str,
        resource: Optional[str] = None,
        justification: Optional[str] = None,
        data_classification: Optional[str] = None,
        outcome: str = "allowed",
        **kwargs
    ):
        """Log a compliance-relevant event for audit trail."""
        self._context.compliance_events.append({
            "event_type": event_type,
            "action": action,
            "resource": resource,
            "justification": justification,
            "data_classification": data_classification,
            "outcome": outcome,
            **kwargs
        })


class AgentWatch:
    """
    AgentWatch client for AI agent observability.
    
    Usage:
        watch = AgentWatch(api_key="your-key")
        
        with watch.trace("customer-support-agent", user_id="user-123") as span:
            result = my_agent.run(task)
            span.log_llm_call(model="claude-3", input_tokens=100, output_tokens=200)
    """
    
    def __init__(
        self,
        api_key: Optional[str] = None,
        api_url: str = "http://localhost:8765",
        environment: str = "production",
        auto_register_agents: bool = True
    ):
        """
        Initialize AgentWatch client.
        
        Args:
            api_key: API key for authentication (or AGENTWATCH_API_KEY env var)
            api_url: AgentWatch API URL
            environment: Environment name (production, staging, development)
            auto_register_agents: Automatically register new agents
        """
        self.api_key = api_key or os.getenv("AGENTWATCH_API_KEY", "demo-key")
        self.api_url = api_url.rstrip("/")
        self.environment = environment
        self.auto_register_agents = auto_register_agents
        self._registered_agents: set = set()
        self._client = httpx.Client(timeout=30.0)
    
    def _headers(self) -> Dict[str, str]:
        """Get request headers."""
        return {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json"
        }
    
    def register_agent(
        self,
        agent_id: str,
        name: str,
        description: Optional[str] = None,
        agent_type: Optional[str] = None,
        owner: Optional[str] = None,
        config: Optional[Dict] = None
    ) -> str:
        """Register an agent with AgentWatch."""
        try:
            response = self._client.post(
                f"{self.api_url}/api/agents",
                headers=self._headers(),
                json={
                    "name": name,
                    "description": description,
                    "agent_type": agent_type,
                    "owner": owner,
                    "config": config
                }
            )
            if response.status_code == 200:
                data = response.json()
                self._registered_agents.add(data["id"])
                return data["id"]
        except Exception as e:
            print(f"Warning: Failed to register agent: {e}")
        
        return agent_id
    
    def _ensure_agent(self, agent_name: str) -> str:
        """Ensure agent is registered, return agent_id."""
        # Simple: use name as ID for now
        agent_id = agent_name.lower().replace(" ", "-")
        
        if agent_id not in self._registered_agents and self.auto_register_agents:
            self.register_agent(agent_id, agent_name)
            self._registered_agents.add(agent_id)
        
        return agent_id
    
    @contextmanager
    def trace(
        self,
        agent_name: str,
        user_id: Optional[str] = None,
        session_id: Optional[str] = None,
        task_type: Optional[str] = None,
        **attributes
    ):
        """
        Create a trace context for an agent execution.
        
        Usage:
            with watch.trace("my-agent", user_id="123") as span:
                result = agent.run()
                span.set_status("success")
        """
        agent_id = self._ensure_agent(agent_name)
        trace_id = str(uuid.uuid4())
        
        context = SpanContext(
            trace_id=trace_id,
            agent_id=agent_id,
            environment=self.environment,
            user_id=user_id,
            session_id=session_id,
            task_type=task_type,
            attributes=attributes
        )
        
        span = Span(context, self)
        
        # Start trace
        try:
            self._client.post(
                f"{self.api_url}/api/traces",
                headers=self._headers(),
                json={
                    "agent_id": agent_id,
                    "environment": self.environment,
                    "user_id": user_id,
                    "session_id": session_id,
                    "task_type": task_type,
                    "attributes": attributes
                }
            )
        except Exception as e:
            print(f"Warning: Failed to start trace: {e}")
        
        try:
            yield span
            # Default to success if not set
            if context.status == "running":
                context.status = "success"
        except Exception as e:
            context.status = "error"
            context.error_message = str(e)
            raise
        finally:
            # End trace
            self._end_trace(span)
    
    def _end_trace(self, span: Span):
        """Send trace completion and all events."""
        ctx = span._context
        
        try:
            # Update trace status
            self._client.patch(
                f"{self.api_url}/api/traces/{ctx.trace_id}",
                headers=self._headers(),
                json={
                    "status": ctx.status,
                    "error_message": ctx.error_message,
                    "output_summary": ctx.output_summary,
                    "attributes": ctx.attributes
                }
            )
            
            # Send events
            for event in ctx.events:
                event["trace_id"] = ctx.trace_id
                self._client.post(
                    f"{self.api_url}/api/events",
                    headers=self._headers(),
                    json=event
                )
            
            # Send costs
            for cost in ctx.costs:
                cost["trace_id"] = ctx.trace_id
                self._client.post(
                    f"{self.api_url}/api/costs",
                    headers=self._headers(),
                    json=cost
                )
            
            # Send compliance events
            for ce in ctx.compliance_events:
                ce["trace_id"] = ctx.trace_id
                self._client.post(
                    f"{self.api_url}/api/compliance",
                    headers=self._headers(),
                    json=ce
                )
                
        except Exception as e:
            print(f"Warning: Failed to end trace: {e}")
    
    def create_alert(
        self,
        title: str,
        severity: str = "warning",
        alert_type: str = "custom",
        description: Optional[str] = None,
        agent_id: Optional[str] = None,
        details: Optional[Dict] = None
    ):
        """Create a custom alert."""
        try:
            self._client.post(
                f"{self.api_url}/api/alerts",
                headers=self._headers(),
                json={
                    "title": title,
                    "severity": severity,
                    "alert_type": alert_type,
                    "description": description,
                    "agent_id": agent_id,
                    "details": details
                }
            )
        except Exception as e:
            print(f"Warning: Failed to create alert: {e}")
    
    def close(self):
        """Close the client."""
        self._client.close()
    
    def __enter__(self):
        return self
    
    def __exit__(self, *args):
        self.close()
