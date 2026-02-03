"""
AgentWatch API Schemas (Pydantic)

Request/response models for the API.
"""

from datetime import datetime
from typing import Optional, List, Dict, Any
from pydantic import BaseModel, Field
from enum import Enum


# Enums
class TraceStatus(str, Enum):
    RUNNING = "running"
    SUCCESS = "success"
    ERROR = "error"
    TIMEOUT = "timeout"


class EventType(str, Enum):
    TOOL_CALL = "tool_call"
    LLM_CALL = "llm_call"
    DECISION = "decision"
    ERROR = "error"
    CUSTOM = "custom"


class CostCategory(str, Enum):
    LLM = "llm"
    TOOL = "tool"
    API = "api"
    COMPUTE = "compute"


class Severity(str, Enum):
    INFO = "info"
    WARNING = "warning"
    ERROR = "error"
    CRITICAL = "critical"


class DataClassification(str, Enum):
    PUBLIC = "public"
    INTERNAL = "internal"
    CONFIDENTIAL = "confidential"
    RESTRICTED = "restricted"


# Agent Schemas
class AgentCreate(BaseModel):
    name: str
    description: Optional[str] = None
    agent_type: Optional[str] = None
    owner: Optional[str] = None
    config: Optional[Dict[str, Any]] = None


class AgentResponse(BaseModel):
    id: str
    name: str
    description: Optional[str]
    agent_type: Optional[str]
    owner: Optional[str]
    created_at: datetime
    is_active: bool
    config: Optional[Dict[str, Any]]

    class Config:
        from_attributes = True


# Trace Schemas
class TraceCreate(BaseModel):
    agent_id: str
    parent_trace_id: Optional[str] = None
    environment: str = "production"
    user_id: Optional[str] = None
    session_id: Optional[str] = None
    task_type: Optional[str] = None
    input_summary: Optional[str] = None
    attributes: Optional[Dict[str, Any]] = None


class TraceUpdate(BaseModel):
    status: Optional[TraceStatus] = None
    error_message: Optional[str] = None
    error_type: Optional[str] = None
    output_summary: Optional[str] = None
    attributes: Optional[Dict[str, Any]] = None


class TraceResponse(BaseModel):
    id: str
    agent_id: str
    parent_trace_id: Optional[str]
    started_at: datetime
    ended_at: Optional[datetime]
    duration_ms: Optional[int]
    environment: str
    user_id: Optional[str]
    session_id: Optional[str]
    task_type: Optional[str]
    status: str
    error_message: Optional[str]
    input_summary: Optional[str]
    output_summary: Optional[str]
    attributes: Optional[Dict[str, Any]]

    class Config:
        from_attributes = True


# Event Schemas
class EventCreate(BaseModel):
    trace_id: str
    event_type: EventType
    event_name: Optional[str] = None
    input_data: Optional[Dict[str, Any]] = None
    output_data: Optional[Dict[str, Any]] = None
    duration_ms: Optional[int] = None
    status: Optional[str] = None
    model: Optional[str] = None
    input_tokens: Optional[int] = None
    output_tokens: Optional[int] = None
    attributes: Optional[Dict[str, Any]] = None


class EventResponse(BaseModel):
    id: str
    trace_id: str
    timestamp: datetime
    event_type: str
    event_name: Optional[str]
    duration_ms: Optional[int]
    status: Optional[str]
    model: Optional[str]
    input_tokens: Optional[int]
    output_tokens: Optional[int]

    class Config:
        from_attributes = True


# Cost Schemas
class CostCreate(BaseModel):
    trace_id: str
    amount: float
    currency: str = "USD"
    category: CostCategory
    subcategory: Optional[str] = None
    model: Optional[str] = None
    input_tokens: Optional[int] = None
    output_tokens: Optional[int] = None
    customer_id: Optional[str] = None
    team_id: Optional[str] = None


class CostResponse(BaseModel):
    id: str
    trace_id: str
    timestamp: datetime
    amount: float
    currency: str
    category: str
    model: Optional[str]
    customer_id: Optional[str]

    class Config:
        from_attributes = True


# Compliance Schemas
class ComplianceEventCreate(BaseModel):
    trace_id: str
    event_type: str
    action: str
    resource: Optional[str] = None
    resource_type: Optional[str] = None
    justification: Optional[str] = None
    data_classification: Optional[DataClassification] = None
    actor_type: str = "agent"
    actor_id: Optional[str] = None
    outcome: str = "allowed"
    request_data: Optional[Dict[str, Any]] = None
    response_data: Optional[Dict[str, Any]] = None


class ComplianceEventResponse(BaseModel):
    id: str
    trace_id: str
    timestamp: datetime
    event_type: str
    action: str
    resource: Optional[str]
    data_classification: Optional[str]
    outcome: str
    justification: Optional[str]

    class Config:
        from_attributes = True


# Alert Schemas
class AlertCreate(BaseModel):
    alert_type: str
    severity: Severity
    title: str
    description: Optional[str] = None
    agent_id: Optional[str] = None
    trace_id: Optional[str] = None
    details: Optional[Dict[str, Any]] = None


class AlertResponse(BaseModel):
    id: str
    timestamp: datetime
    alert_type: str
    severity: str
    title: str
    description: Optional[str]
    agent_id: Optional[str]
    status: str

    class Config:
        from_attributes = True


# Analytics Schemas
class MetricsSummary(BaseModel):
    total_traces: int
    success_rate: float
    error_rate: float
    avg_duration_ms: float
    total_cost: float
    total_tokens: int


class AgentMetrics(BaseModel):
    agent_id: str
    agent_name: str
    trace_count: int
    success_rate: float
    avg_duration_ms: float
    total_cost: float


class TimeSeriesPoint(BaseModel):
    timestamp: datetime
    value: float


class CostBreakdown(BaseModel):
    category: str
    amount: float
    percentage: float


class DashboardData(BaseModel):
    summary: MetricsSummary
    agent_metrics: List[AgentMetrics]
    traces_over_time: List[TimeSeriesPoint]
    cost_over_time: List[TimeSeriesPoint]
    cost_breakdown: List[CostBreakdown]
    recent_alerts: List[AlertResponse]
    recent_errors: List[TraceResponse]


# Bulk Ingest Schemas
class BulkIngestRequest(BaseModel):
    """For high-volume telemetry ingestion."""
    traces: Optional[List[TraceCreate]] = None
    events: Optional[List[EventCreate]] = None
    costs: Optional[List[CostCreate]] = None
    compliance_events: Optional[List[ComplianceEventCreate]] = None


class BulkIngestResponse(BaseModel):
    traces_created: int = 0
    events_created: int = 0
    costs_created: int = 0
    compliance_events_created: int = 0
    errors: List[str] = []
