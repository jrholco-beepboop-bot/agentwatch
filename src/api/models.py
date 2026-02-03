"""
AgentWatch Database Models

Core data models for agent telemetry, compliance, and analytics.
"""

from datetime import datetime
from typing import Optional
from sqlalchemy import Column, String, Float, Integer, DateTime, Text, Boolean, ForeignKey, JSON, Index
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import relationship

Base = declarative_base()


class Agent(Base):
    """Registered agents in the system."""
    __tablename__ = "agents"
    
    id = Column(String(36), primary_key=True)
    name = Column(String(255), nullable=False, index=True)
    description = Column(Text)
    agent_type = Column(String(50))  # e.g., "support", "sales", "ops"
    owner = Column(String(255))
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    is_active = Column(Boolean, default=True)
    config = Column(JSON)  # Agent configuration metadata
    
    # Relationships
    traces = relationship("Trace", back_populates="agent")
    policies = relationship("Policy", back_populates="agent")


class Trace(Base):
    """Individual execution traces from agents."""
    __tablename__ = "traces"
    
    id = Column(String(36), primary_key=True)
    agent_id = Column(String(36), ForeignKey("agents.id"), nullable=False, index=True)
    parent_trace_id = Column(String(36), ForeignKey("traces.id"), nullable=True)
    
    # Timing
    started_at = Column(DateTime, nullable=False, index=True)
    ended_at = Column(DateTime)
    duration_ms = Column(Integer)
    
    # Context
    environment = Column(String(50), default="production", index=True)
    user_id = Column(String(255), index=True)
    session_id = Column(String(255))
    task_type = Column(String(100), index=True)
    
    # Status
    status = Column(String(20), default="running", index=True)  # running, success, error, timeout
    error_message = Column(Text)
    error_type = Column(String(100))
    
    # Metadata
    input_summary = Column(Text)  # Truncated/redacted input
    output_summary = Column(Text)  # Truncated/redacted output
    attributes = Column(JSON)  # Custom key-value pairs
    
    # Relationships
    agent = relationship("Agent", back_populates="traces")
    events = relationship("Event", back_populates="trace")
    costs = relationship("Cost", back_populates="trace")
    compliance_events = relationship("ComplianceEvent", back_populates="trace")
    
    __table_args__ = (
        Index("ix_traces_agent_started", "agent_id", "started_at"),
        Index("ix_traces_status_started", "status", "started_at"),
    )


class Event(Base):
    """Individual events within a trace (tool calls, decisions, etc.)."""
    __tablename__ = "events"
    
    id = Column(String(36), primary_key=True)
    trace_id = Column(String(36), ForeignKey("traces.id"), nullable=False, index=True)
    
    timestamp = Column(DateTime, nullable=False, index=True)
    event_type = Column(String(50), nullable=False, index=True)  # tool_call, llm_call, decision, error
    event_name = Column(String(255))
    
    # Event details
    input_data = Column(JSON)
    output_data = Column(JSON)
    duration_ms = Column(Integer)
    status = Column(String(20))
    
    # For LLM calls
    model = Column(String(100))
    input_tokens = Column(Integer)
    output_tokens = Column(Integer)
    
    # Metadata
    attributes = Column(JSON)
    
    # Relationships
    trace = relationship("Trace", back_populates="events")


class Cost(Base):
    """Cost tracking for agent operations."""
    __tablename__ = "costs"
    
    id = Column(String(36), primary_key=True)
    trace_id = Column(String(36), ForeignKey("traces.id"), nullable=False, index=True)
    
    timestamp = Column(DateTime, nullable=False, index=True)
    amount = Column(Float, nullable=False)
    currency = Column(String(3), default="USD")
    
    # Categorization
    category = Column(String(50), index=True)  # llm, tool, api, compute
    subcategory = Column(String(100))
    model = Column(String(100))
    
    # Token details (for LLM costs)
    input_tokens = Column(Integer)
    output_tokens = Column(Integer)
    
    # Attribution
    customer_id = Column(String(255), index=True)
    team_id = Column(String(255), index=True)
    
    # Relationships
    trace = relationship("Trace", back_populates="costs")
    
    __table_args__ = (
        Index("ix_costs_category_timestamp", "category", "timestamp"),
        Index("ix_costs_customer_timestamp", "customer_id", "timestamp"),
    )


class ComplianceEvent(Base):
    """Compliance and audit trail events."""
    __tablename__ = "compliance_events"
    
    id = Column(String(36), primary_key=True)
    trace_id = Column(String(36), ForeignKey("traces.id"), nullable=False, index=True)
    
    timestamp = Column(DateTime, nullable=False, index=True)
    event_type = Column(String(50), nullable=False, index=True)  # data_access, pii_handling, decision, external_call
    
    # What happened
    action = Column(String(100), nullable=False)
    resource = Column(String(255))
    resource_type = Column(String(50))
    
    # Context
    justification = Column(Text)
    data_classification = Column(String(50))  # public, internal, confidential, restricted
    
    # Actor
    actor_type = Column(String(20))  # agent, user, system
    actor_id = Column(String(255))
    
    # Outcome
    outcome = Column(String(20))  # allowed, denied, flagged
    policy_id = Column(String(36))
    
    # Full audit data
    request_data = Column(JSON)
    response_data = Column(JSON)
    
    # Relationships
    trace = relationship("Trace", back_populates="compliance_events")
    
    __table_args__ = (
        Index("ix_compliance_type_timestamp", "event_type", "timestamp"),
    )


class Policy(Base):
    """Policies and guardrails for agents."""
    __tablename__ = "policies"
    
    id = Column(String(36), primary_key=True)
    agent_id = Column(String(36), ForeignKey("agents.id"), nullable=True)  # null = global policy
    
    name = Column(String(255), nullable=False)
    description = Column(Text)
    policy_type = Column(String(50), nullable=False)  # cost_limit, allowed_tools, data_handling, rate_limit
    
    # Policy definition
    config = Column(JSON, nullable=False)  # Policy-specific configuration
    
    # Status
    is_active = Column(Boolean, default=True)
    severity = Column(String(20), default="medium")  # low, medium, high, critical
    action_on_violation = Column(String(20), default="log")  # log, warn, block
    
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    # Relationships
    agent = relationship("Agent", back_populates="policies")


class Alert(Base):
    """Alerts generated by the system."""
    __tablename__ = "alerts"
    
    id = Column(String(36), primary_key=True)
    
    timestamp = Column(DateTime, nullable=False, index=True)
    alert_type = Column(String(50), nullable=False, index=True)  # anomaly, policy_violation, error_spike, cost_spike
    severity = Column(String(20), nullable=False, index=True)  # info, warning, error, critical
    
    title = Column(String(255), nullable=False)
    description = Column(Text)
    
    # Context
    agent_id = Column(String(36), index=True)
    trace_id = Column(String(36))
    policy_id = Column(String(36))
    
    # Status
    status = Column(String(20), default="open", index=True)  # open, acknowledged, resolved
    acknowledged_at = Column(DateTime)
    resolved_at = Column(DateTime)
    acknowledged_by = Column(String(255))
    
    # Details
    details = Column(JSON)


class AggregatedMetrics(Base):
    """Pre-aggregated metrics for fast dashboard queries."""
    __tablename__ = "aggregated_metrics"
    
    id = Column(String(36), primary_key=True)
    
    # Time bucket
    bucket_start = Column(DateTime, nullable=False, index=True)
    bucket_size = Column(String(10), nullable=False)  # 1m, 5m, 1h, 1d
    
    # Dimensions
    agent_id = Column(String(36), index=True)
    environment = Column(String(50))
    task_type = Column(String(100))
    
    # Metrics
    trace_count = Column(Integer, default=0)
    success_count = Column(Integer, default=0)
    error_count = Column(Integer, default=0)
    
    total_duration_ms = Column(Integer, default=0)
    avg_duration_ms = Column(Float)
    p50_duration_ms = Column(Float)
    p95_duration_ms = Column(Float)
    p99_duration_ms = Column(Float)
    
    total_cost = Column(Float, default=0)
    total_input_tokens = Column(Integer, default=0)
    total_output_tokens = Column(Integer, default=0)
    
    __table_args__ = (
        Index("ix_agg_bucket_agent", "bucket_start", "agent_id"),
    )
