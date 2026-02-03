"""
AgentWatch SDK

Simple SDK for instrumenting AI agents with AgentWatch telemetry.

Usage:
    from agentwatch import AgentWatch
    
    watch = AgentWatch(api_key="your-key")
    
    with watch.trace("my-agent") as span:
        result = my_agent.run(task)
        span.log_llm_call(model="claude-3", input_tokens=100, output_tokens=200)
"""

from .client import AgentWatch
from .span import Span

__all__ = ["AgentWatch", "Span"]
__version__ = "0.1.0"
