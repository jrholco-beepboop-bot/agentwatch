"""
AgentWatch API Server

FastAPI application for agent telemetry ingestion and analytics.
"""

import os
import uuid
from datetime import datetime, timedelta
from typing import Optional, List
from contextlib import asynccontextmanager

from fastapi import FastAPI, HTTPException, Depends, Query
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import HTMLResponse
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func, and_, desc
from sqlalchemy.orm import selectinload

from .database import init_db, get_db, engine
from .models import Agent, Trace, Event, Cost, ComplianceEvent, Alert, AggregatedMetrics
from .schemas import (
    AgentCreate, AgentResponse,
    TraceCreate, TraceUpdate, TraceResponse,
    EventCreate, EventResponse,
    CostCreate, CostResponse,
    ComplianceEventCreate, ComplianceEventResponse,
    AlertCreate, AlertResponse,
    MetricsSummary, AgentMetrics, TimeSeriesPoint, CostBreakdown, DashboardData,
    BulkIngestRequest, BulkIngestResponse,
    TraceStatus
)


# Model pricing (cost per 1K tokens)
MODEL_PRICING = {
    "claude-3-opus": {"input": 0.015, "output": 0.075},
    "claude-3-sonnet": {"input": 0.003, "output": 0.015},
    "claude-3-haiku": {"input": 0.00025, "output": 0.00125},
    "claude-3-5-sonnet": {"input": 0.003, "output": 0.015},
    "gpt-4": {"input": 0.03, "output": 0.06},
    "gpt-4-turbo": {"input": 0.01, "output": 0.03},
    "gpt-4o": {"input": 0.005, "output": 0.015},
    "gpt-3.5-turbo": {"input": 0.0005, "output": 0.0015},
    "gemini-pro": {"input": 0.00025, "output": 0.0005},
    "gemini-1.5-pro": {"input": 0.00125, "output": 0.005},
}


def calculate_cost(model: str, input_tokens: int, output_tokens: int) -> float:
    """Calculate cost based on model and token counts."""
    pricing = MODEL_PRICING.get(model, {"input": 0.001, "output": 0.002})
    input_cost = (input_tokens / 1000) * pricing["input"]
    output_cost = (output_tokens / 1000) * pricing["output"]
    return round(input_cost + output_cost, 6)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifespan handler."""
    await init_db()
    yield
    await engine.dispose()


# Create FastAPI app
app = FastAPI(
    title="AgentWatch API",
    description="Observability & Governance Platform for AI Agents",
    version="0.1.0",
    lifespan=lifespan
)

# CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# ============================================================================
# Health Check
# ============================================================================

@app.get("/health")
async def health_check():
    """Health check endpoint."""
    return {"status": "healthy", "timestamp": datetime.utcnow().isoformat()}


@app.get("/")
async def root():
    """Root endpoint with API info."""
    return {
        "name": "AgentWatch API",
        "version": "0.1.0",
        "docs": "/docs",
        "dashboard": "/dashboard"
    }


# ============================================================================
# Agent Endpoints
# ============================================================================

@app.post("/api/agents", response_model=AgentResponse)
async def create_agent(agent: AgentCreate, db: AsyncSession = Depends(get_db)):
    """Register a new agent."""
    db_agent = Agent(
        id=str(uuid.uuid4()),
        name=agent.name,
        description=agent.description,
        agent_type=agent.agent_type,
        owner=agent.owner,
        config=agent.config
    )
    db.add(db_agent)
    await db.flush()
    return db_agent


@app.get("/api/agents", response_model=List[AgentResponse])
async def list_agents(
    skip: int = 0,
    limit: int = 100,
    db: AsyncSession = Depends(get_db)
):
    """List all registered agents."""
    result = await db.execute(
        select(Agent).where(Agent.is_active == True).offset(skip).limit(limit)
    )
    return result.scalars().all()


@app.get("/api/agents/{agent_id}", response_model=AgentResponse)
async def get_agent(agent_id: str, db: AsyncSession = Depends(get_db)):
    """Get a specific agent."""
    result = await db.execute(select(Agent).where(Agent.id == agent_id))
    agent = result.scalar_one_or_none()
    if not agent:
        raise HTTPException(status_code=404, detail="Agent not found")
    return agent


# ============================================================================
# Trace Endpoints
# ============================================================================

@app.post("/api/traces", response_model=TraceResponse)
async def create_trace(trace: TraceCreate, db: AsyncSession = Depends(get_db)):
    """Start a new trace."""
    db_trace = Trace(
        id=str(uuid.uuid4()),
        agent_id=trace.agent_id,
        parent_trace_id=trace.parent_trace_id,
        started_at=datetime.utcnow(),
        environment=trace.environment,
        user_id=trace.user_id,
        session_id=trace.session_id,
        task_type=trace.task_type,
        input_summary=trace.input_summary,
        attributes=trace.attributes,
        status="running"
    )
    db.add(db_trace)
    await db.flush()
    return db_trace


@app.patch("/api/traces/{trace_id}", response_model=TraceResponse)
async def update_trace(
    trace_id: str,
    trace_update: TraceUpdate,
    db: AsyncSession = Depends(get_db)
):
    """Update/complete a trace."""
    result = await db.execute(select(Trace).where(Trace.id == trace_id))
    trace = result.scalar_one_or_none()
    if not trace:
        raise HTTPException(status_code=404, detail="Trace not found")
    
    if trace_update.status:
        trace.status = trace_update.status.value
        if trace_update.status in [TraceStatus.SUCCESS, TraceStatus.ERROR, TraceStatus.TIMEOUT]:
            trace.ended_at = datetime.utcnow()
            if trace.started_at:
                trace.duration_ms = int((trace.ended_at - trace.started_at).total_seconds() * 1000)
    
    if trace_update.error_message:
        trace.error_message = trace_update.error_message
    if trace_update.error_type:
        trace.error_type = trace_update.error_type
    if trace_update.output_summary:
        trace.output_summary = trace_update.output_summary
    if trace_update.attributes:
        trace.attributes = {**(trace.attributes or {}), **trace_update.attributes}
    
    await db.flush()
    return trace


@app.get("/api/traces", response_model=List[TraceResponse])
async def list_traces(
    agent_id: Optional[str] = None,
    status: Optional[str] = None,
    environment: Optional[str] = None,
    since: Optional[datetime] = None,
    skip: int = 0,
    limit: int = 100,
    db: AsyncSession = Depends(get_db)
):
    """List traces with optional filters."""
    query = select(Trace)
    
    conditions = []
    if agent_id:
        conditions.append(Trace.agent_id == agent_id)
    if status:
        conditions.append(Trace.status == status)
    if environment:
        conditions.append(Trace.environment == environment)
    if since:
        conditions.append(Trace.started_at >= since)
    
    if conditions:
        query = query.where(and_(*conditions))
    
    query = query.order_by(desc(Trace.started_at)).offset(skip).limit(limit)
    result = await db.execute(query)
    return result.scalars().all()


@app.get("/api/traces/{trace_id}", response_model=TraceResponse)
async def get_trace(trace_id: str, db: AsyncSession = Depends(get_db)):
    """Get a specific trace with all events."""
    result = await db.execute(
        select(Trace)
        .options(selectinload(Trace.events), selectinload(Trace.costs))
        .where(Trace.id == trace_id)
    )
    trace = result.scalar_one_or_none()
    if not trace:
        raise HTTPException(status_code=404, detail="Trace not found")
    return trace


# ============================================================================
# Event Endpoints
# ============================================================================

@app.post("/api/events", response_model=EventResponse)
async def create_event(event: EventCreate, db: AsyncSession = Depends(get_db)):
    """Log an event within a trace."""
    db_event = Event(
        id=str(uuid.uuid4()),
        trace_id=event.trace_id,
        timestamp=datetime.utcnow(),
        event_type=event.event_type.value,
        event_name=event.event_name,
        input_data=event.input_data,
        output_data=event.output_data,
        duration_ms=event.duration_ms,
        status=event.status,
        model=event.model,
        input_tokens=event.input_tokens,
        output_tokens=event.output_tokens,
        attributes=event.attributes
    )
    db.add(db_event)
    
    # Auto-create cost for LLM calls
    if event.event_type.value == "llm_call" and event.model and event.input_tokens and event.output_tokens:
        cost_amount = calculate_cost(event.model, event.input_tokens, event.output_tokens)
        db_cost = Cost(
            id=str(uuid.uuid4()),
            trace_id=event.trace_id,
            timestamp=datetime.utcnow(),
            amount=cost_amount,
            currency="USD",
            category="llm",
            model=event.model,
            input_tokens=event.input_tokens,
            output_tokens=event.output_tokens
        )
        db.add(db_cost)
    
    await db.flush()
    return db_event


@app.get("/api/events", response_model=List[EventResponse])
async def list_events(
    trace_id: str,
    db: AsyncSession = Depends(get_db)
):
    """List events for a trace."""
    result = await db.execute(
        select(Event)
        .where(Event.trace_id == trace_id)
        .order_by(Event.timestamp)
    )
    return result.scalars().all()


# ============================================================================
# Cost Endpoints
# ============================================================================

@app.post("/api/costs", response_model=CostResponse)
async def create_cost(cost: CostCreate, db: AsyncSession = Depends(get_db)):
    """Log a cost entry."""
    db_cost = Cost(
        id=str(uuid.uuid4()),
        trace_id=cost.trace_id,
        timestamp=datetime.utcnow(),
        amount=cost.amount,
        currency=cost.currency,
        category=cost.category.value,
        subcategory=cost.subcategory,
        model=cost.model,
        input_tokens=cost.input_tokens,
        output_tokens=cost.output_tokens,
        customer_id=cost.customer_id,
        team_id=cost.team_id
    )
    db.add(db_cost)
    await db.flush()
    return db_cost


@app.get("/api/costs/summary")
async def get_cost_summary(
    since: Optional[datetime] = None,
    agent_id: Optional[str] = None,
    db: AsyncSession = Depends(get_db)
):
    """Get cost summary."""
    if not since:
        since = datetime.utcnow() - timedelta(days=30)
    
    query = select(
        func.sum(Cost.amount).label("total"),
        func.count(Cost.id).label("count"),
        Cost.category
    ).where(Cost.timestamp >= since)
    
    if agent_id:
        query = query.join(Trace).where(Trace.agent_id == agent_id)
    
    query = query.group_by(Cost.category)
    result = await db.execute(query)
    
    breakdown = []
    total = 0
    for row in result:
        breakdown.append({
            "category": row.category,
            "amount": float(row.total or 0),
            "count": row.count
        })
        total += float(row.total or 0)
    
    return {
        "total": round(total, 2),
        "currency": "USD",
        "since": since.isoformat(),
        "breakdown": breakdown
    }


# ============================================================================
# Compliance Endpoints
# ============================================================================

@app.post("/api/compliance", response_model=ComplianceEventResponse)
async def create_compliance_event(
    event: ComplianceEventCreate,
    db: AsyncSession = Depends(get_db)
):
    """Log a compliance event."""
    db_event = ComplianceEvent(
        id=str(uuid.uuid4()),
        trace_id=event.trace_id,
        timestamp=datetime.utcnow(),
        event_type=event.event_type,
        action=event.action,
        resource=event.resource,
        resource_type=event.resource_type,
        justification=event.justification,
        data_classification=event.data_classification.value if event.data_classification else None,
        actor_type=event.actor_type,
        actor_id=event.actor_id,
        outcome=event.outcome,
        request_data=event.request_data,
        response_data=event.response_data
    )
    db.add(db_event)
    await db.flush()
    return db_event


@app.get("/api/compliance", response_model=List[ComplianceEventResponse])
async def list_compliance_events(
    trace_id: Optional[str] = None,
    event_type: Optional[str] = None,
    since: Optional[datetime] = None,
    skip: int = 0,
    limit: int = 100,
    db: AsyncSession = Depends(get_db)
):
    """List compliance events."""
    query = select(ComplianceEvent)
    
    conditions = []
    if trace_id:
        conditions.append(ComplianceEvent.trace_id == trace_id)
    if event_type:
        conditions.append(ComplianceEvent.event_type == event_type)
    if since:
        conditions.append(ComplianceEvent.timestamp >= since)
    
    if conditions:
        query = query.where(and_(*conditions))
    
    query = query.order_by(desc(ComplianceEvent.timestamp)).offset(skip).limit(limit)
    result = await db.execute(query)
    return result.scalars().all()


@app.get("/api/compliance/report")
async def generate_compliance_report(
    since: Optional[datetime] = None,
    until: Optional[datetime] = None,
    db: AsyncSession = Depends(get_db)
):
    """Generate a compliance audit report."""
    if not since:
        since = datetime.utcnow() - timedelta(days=30)
    if not until:
        until = datetime.utcnow()
    
    # Get event counts by type
    event_counts = await db.execute(
        select(
            ComplianceEvent.event_type,
            func.count(ComplianceEvent.id).label("count")
        )
        .where(and_(
            ComplianceEvent.timestamp >= since,
            ComplianceEvent.timestamp <= until
        ))
        .group_by(ComplianceEvent.event_type)
    )
    
    # Get outcome distribution
    outcomes = await db.execute(
        select(
            ComplianceEvent.outcome,
            func.count(ComplianceEvent.id).label("count")
        )
        .where(and_(
            ComplianceEvent.timestamp >= since,
            ComplianceEvent.timestamp <= until
        ))
        .group_by(ComplianceEvent.outcome)
    )
    
    # Get data classification distribution
    classifications = await db.execute(
        select(
            ComplianceEvent.data_classification,
            func.count(ComplianceEvent.id).label("count")
        )
        .where(and_(
            ComplianceEvent.timestamp >= since,
            ComplianceEvent.timestamp <= until,
            ComplianceEvent.data_classification.isnot(None)
        ))
        .group_by(ComplianceEvent.data_classification)
    )
    
    return {
        "report_period": {
            "start": since.isoformat(),
            "end": until.isoformat()
        },
        "event_types": {row.event_type: row.count for row in event_counts},
        "outcomes": {row.outcome: row.count for row in outcomes},
        "data_classifications": {row.data_classification: row.count for row in classifications},
        "generated_at": datetime.utcnow().isoformat()
    }


# ============================================================================
# Alert Endpoints
# ============================================================================

@app.post("/api/alerts", response_model=AlertResponse)
async def create_alert(alert: AlertCreate, db: AsyncSession = Depends(get_db)):
    """Create a new alert."""
    db_alert = Alert(
        id=str(uuid.uuid4()),
        timestamp=datetime.utcnow(),
        alert_type=alert.alert_type,
        severity=alert.severity.value,
        title=alert.title,
        description=alert.description,
        agent_id=alert.agent_id,
        trace_id=alert.trace_id,
        details=alert.details
    )
    db.add(db_alert)
    await db.flush()
    return db_alert


@app.get("/api/alerts", response_model=List[AlertResponse])
async def list_alerts(
    status: Optional[str] = "open",
    severity: Optional[str] = None,
    since: Optional[datetime] = None,
    skip: int = 0,
    limit: int = 50,
    db: AsyncSession = Depends(get_db)
):
    """List alerts."""
    query = select(Alert)
    
    conditions = []
    if status:
        conditions.append(Alert.status == status)
    if severity:
        conditions.append(Alert.severity == severity)
    if since:
        conditions.append(Alert.timestamp >= since)
    
    if conditions:
        query = query.where(and_(*conditions))
    
    query = query.order_by(desc(Alert.timestamp)).offset(skip).limit(limit)
    result = await db.execute(query)
    return result.scalars().all()


@app.patch("/api/alerts/{alert_id}")
async def update_alert_status(
    alert_id: str,
    status: str,
    db: AsyncSession = Depends(get_db)
):
    """Update alert status."""
    result = await db.execute(select(Alert).where(Alert.id == alert_id))
    alert = result.scalar_one_or_none()
    if not alert:
        raise HTTPException(status_code=404, detail="Alert not found")
    
    alert.status = status
    if status == "acknowledged":
        alert.acknowledged_at = datetime.utcnow()
    elif status == "resolved":
        alert.resolved_at = datetime.utcnow()
    
    await db.flush()
    return {"status": "updated"}


# ============================================================================
# Analytics / Dashboard Endpoints
# ============================================================================

@app.get("/api/analytics/summary")
async def get_analytics_summary(
    since: Optional[datetime] = None,
    agent_id: Optional[str] = None,
    db: AsyncSession = Depends(get_db)
):
    """Get summary analytics for dashboard."""
    if not since:
        since = datetime.utcnow() - timedelta(days=7)
    
    # Base query conditions
    conditions = [Trace.started_at >= since]
    if agent_id:
        conditions.append(Trace.agent_id == agent_id)
    
    # Get trace counts
    trace_stats = await db.execute(
        select(
            func.count(Trace.id).label("total"),
            func.sum(func.cast(Trace.status == "success", Integer)).label("success"),
            func.sum(func.cast(Trace.status == "error", Integer)).label("errors"),
            func.avg(Trace.duration_ms).label("avg_duration")
        ).where(and_(*conditions))
    )
    stats = trace_stats.one()
    
    # Get total cost
    cost_conditions = [Cost.timestamp >= since]
    if agent_id:
        cost_conditions.append(Trace.agent_id == agent_id)
        cost_query = select(func.sum(Cost.amount)).join(Trace).where(and_(*cost_conditions))
    else:
        cost_query = select(func.sum(Cost.amount)).where(Cost.timestamp >= since)
    
    total_cost = await db.execute(cost_query)
    cost = total_cost.scalar() or 0
    
    # Get token counts
    token_query = select(
        func.sum(Cost.input_tokens).label("input"),
        func.sum(Cost.output_tokens).label("output")
    ).where(Cost.timestamp >= since)
    tokens = await db.execute(token_query)
    token_data = tokens.one()
    
    total = stats.total or 0
    success = stats.success or 0
    errors = stats.errors or 0
    
    return {
        "total_traces": total,
        "success_count": success,
        "error_count": errors,
        "success_rate": round((success / total * 100) if total > 0 else 0, 1),
        "error_rate": round((errors / total * 100) if total > 0 else 0, 1),
        "avg_duration_ms": round(stats.avg_duration or 0, 0),
        "total_cost": round(float(cost), 2),
        "total_input_tokens": token_data.input or 0,
        "total_output_tokens": token_data.output or 0,
        "period_start": since.isoformat()
    }


@app.get("/api/analytics/agents")
async def get_agent_analytics(
    since: Optional[datetime] = None,
    db: AsyncSession = Depends(get_db)
):
    """Get per-agent analytics."""
    if not since:
        since = datetime.utcnow() - timedelta(days=7)
    
    result = await db.execute(
        select(
            Agent.id,
            Agent.name,
            func.count(Trace.id).label("trace_count"),
            func.sum(func.cast(Trace.status == "success", Integer)).label("success_count"),
            func.avg(Trace.duration_ms).label("avg_duration")
        )
        .join(Trace, Agent.id == Trace.agent_id)
        .where(Trace.started_at >= since)
        .group_by(Agent.id, Agent.name)
        .order_by(desc("trace_count"))
    )
    
    agents = []
    for row in result:
        total = row.trace_count or 0
        success = row.success_count or 0
        agents.append({
            "agent_id": row.id,
            "agent_name": row.name,
            "trace_count": total,
            "success_rate": round((success / total * 100) if total > 0 else 0, 1),
            "avg_duration_ms": round(row.avg_duration or 0, 0)
        })
    
    return agents


@app.get("/api/analytics/timeseries")
async def get_timeseries(
    metric: str = "traces",  # traces, cost, errors
    since: Optional[datetime] = None,
    bucket: str = "1h",  # 1h, 1d
    db: AsyncSession = Depends(get_db)
):
    """Get time series data for charts."""
    if not since:
        since = datetime.utcnow() - timedelta(days=7)
    
    # Simple hourly aggregation using date functions
    # For SQLite, we'll use strftime
    if metric == "traces":
        result = await db.execute(
            select(
                func.strftime("%Y-%m-%d %H:00:00", Trace.started_at).label("bucket"),
                func.count(Trace.id).label("value")
            )
            .where(Trace.started_at >= since)
            .group_by("bucket")
            .order_by("bucket")
        )
    elif metric == "cost":
        result = await db.execute(
            select(
                func.strftime("%Y-%m-%d %H:00:00", Cost.timestamp).label("bucket"),
                func.sum(Cost.amount).label("value")
            )
            .where(Cost.timestamp >= since)
            .group_by("bucket")
            .order_by("bucket")
        )
    elif metric == "errors":
        result = await db.execute(
            select(
                func.strftime("%Y-%m-%d %H:00:00", Trace.started_at).label("bucket"),
                func.count(Trace.id).label("value")
            )
            .where(and_(Trace.started_at >= since, Trace.status == "error"))
            .group_by("bucket")
            .order_by("bucket")
        )
    else:
        raise HTTPException(status_code=400, detail="Invalid metric")
    
    return [{"timestamp": row.bucket, "value": float(row.value or 0)} for row in result]


# ============================================================================
# Bulk Ingest Endpoint
# ============================================================================

@app.post("/api/ingest", response_model=BulkIngestResponse)
async def bulk_ingest(request: BulkIngestRequest, db: AsyncSession = Depends(get_db)):
    """Bulk ingest telemetry data."""
    response = BulkIngestResponse()
    
    # Process traces
    if request.traces:
        for trace in request.traces:
            try:
                db_trace = Trace(
                    id=str(uuid.uuid4()),
                    agent_id=trace.agent_id,
                    parent_trace_id=trace.parent_trace_id,
                    started_at=datetime.utcnow(),
                    environment=trace.environment,
                    user_id=trace.user_id,
                    session_id=trace.session_id,
                    task_type=trace.task_type,
                    input_summary=trace.input_summary,
                    attributes=trace.attributes,
                    status="running"
                )
                db.add(db_trace)
                response.traces_created += 1
            except Exception as e:
                response.errors.append(f"Trace error: {str(e)}")
    
    # Process events
    if request.events:
        for event in request.events:
            try:
                db_event = Event(
                    id=str(uuid.uuid4()),
                    trace_id=event.trace_id,
                    timestamp=datetime.utcnow(),
                    event_type=event.event_type.value,
                    event_name=event.event_name,
                    input_data=event.input_data,
                    output_data=event.output_data,
                    duration_ms=event.duration_ms,
                    status=event.status,
                    model=event.model,
                    input_tokens=event.input_tokens,
                    output_tokens=event.output_tokens,
                    attributes=event.attributes
                )
                db.add(db_event)
                response.events_created += 1
            except Exception as e:
                response.errors.append(f"Event error: {str(e)}")
    
    # Process costs
    if request.costs:
        for cost in request.costs:
            try:
                db_cost = Cost(
                    id=str(uuid.uuid4()),
                    trace_id=cost.trace_id,
                    timestamp=datetime.utcnow(),
                    amount=cost.amount,
                    currency=cost.currency,
                    category=cost.category.value,
                    subcategory=cost.subcategory,
                    model=cost.model,
                    input_tokens=cost.input_tokens,
                    output_tokens=cost.output_tokens,
                    customer_id=cost.customer_id,
                    team_id=cost.team_id
                )
                db.add(db_cost)
                response.costs_created += 1
            except Exception as e:
                response.errors.append(f"Cost error: {str(e)}")
    
    await db.flush()
    return response


# ============================================================================
# Run Server
# ============================================================================

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8765)
