"""
AgentWatch Span

Re-export from client for cleaner imports.
"""

from .client import Span, SpanContext

__all__ = ["Span", "SpanContext"]
