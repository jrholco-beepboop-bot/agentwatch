# 🔍 AgentWatch

**Observability & Governance Platform for AI Agents**

> "Datadog meets SOC2 for AI Agents"

[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)
[![Python 3.10+](https://img.shields.io/badge/python-3.10+-blue.svg)](https://www.python.org/downloads/)

---

## The Problem

Enterprises are deploying AI agents at scale, but they're flying blind:

- **No visibility** into what agents are actually doing
- **No cost tracking** per task, per agent, per customer
- **No compliance** - can't prove agents stayed within bounds
- **No anomaly detection** - rogue agents go unnoticed
- **No audit trail** - SOC2/HIPAA/GDPR requirements unmet

**Result:** Enterprises won't deploy agents in production without trust infrastructure.

## The Solution

**AgentWatch** provides complete observability and governance for AI agent deployments:

### 🎯 Core Features

| Feature | Description |
|---------|-------------|
| **Real-time Monitoring** | Live dashboard showing all agent activity |
| **Cost Attribution** | Track spend per agent, task, customer, team |
| **Compliance Engine** | Automatic audit trail generation |
| **Anomaly Detection** | Alert when agents deviate from expected behavior |
| **Performance Analytics** | Success rates, latency, throughput metrics |
| **Policy Enforcement** | Define guardrails, enforce automatically |

### 💡 Key Value Props

1. **For Compliance Teams:** One-click audit reports for SOC2, HIPAA, GDPR
2. **For Engineering:** Debug agents with full trace visibility
3. **For Finance:** Understand true cost of AI agent operations
4. **For Leadership:** ROI dashboards showing agent value delivered

---

## Architecture

```
┌─────────────────────────────────────────────────────────────┐
│                      Your AI Agents                          │
│  (Claude, GPT, Gemini, LangChain, AutoGPT, Custom, etc.)    │
└─────────────────────┬───────────────────────────────────────┘
                      │ AgentWatch SDK (3 lines of code)
                      ▼
┌─────────────────────────────────────────────────────────────┐
│                   AgentWatch Platform                        │
│  ┌─────────────┐  ┌─────────────┐  ┌─────────────────────┐  │
│  │  Ingestion  │  │  Analytics  │  │  Compliance Engine  │  │
│  │    API      │──│   Engine    │──│   & Audit Trail     │  │
│  └─────────────┘  └─────────────┘  └─────────────────────┘  │
│         │               │                    │               │
│         └───────────────┴────────────────────┘               │
│                         │                                    │
│              ┌──────────▼──────────┐                        │
│              │   SQLite / Postgres  │                        │
│              │      TimeSeries      │                        │
│              └─────────────────────┘                        │
└─────────────────────────────────────────────────────────────┘
                      │
                      ▼
┌─────────────────────────────────────────────────────────────┐
│                    Dashboard & Alerts                        │
│  • Real-time activity feed    • Cost breakdown              │
│  • Anomaly alerts             • Compliance reports          │
│  • Performance graphs         • Policy violations           │
└─────────────────────────────────────────────────────────────┘
```

---

## Quick Start

### 1. Install

```bash
pip install agentwatch
```

### 2. Instrument Your Agent (3 lines)

```python
from agentwatch import AgentWatch

watch = AgentWatch(api_key="your-key")

# Wrap any agent execution
with watch.trace("customer-support-agent", user_id="user-123"):
    result = your_agent.run(task)
    watch.log_cost(input_tokens=150, output_tokens=500, model="claude-3")
```

### 3. View Dashboard

```bash
# Start local dashboard
agentwatch dashboard

# Opens http://localhost:8765
```

---

## Running the MVP

### Prerequisites
- Python 3.10+
- pip

### Setup

```bash
# Clone and enter
git clone https://github.com/jrholco/agentwatch
cd agentwatch

# Install dependencies
pip install -r requirements.txt

# Initialize database
python -m src.api.init_db

# Start the API server
python -m src.api.main

# In another terminal, start the dashboard
python -m src.dashboard.serve
```

### Demo with Sample Data

```bash
# Generate realistic demo data
python demo/generate_demo_data.py

# Open dashboard at http://localhost:8765
```

---

## SDK Reference

### Basic Tracing

```python
from agentwatch import AgentWatch

watch = AgentWatch(
    api_key="aw_live_xxx",  # or set AGENTWATCH_API_KEY env var
    environment="production"
)

# Simple trace
with watch.trace("my-agent") as span:
    span.set_attribute("customer_id", "cust_123")
    result = agent.execute(task)
    span.set_status("success")
```

### Cost Tracking

```python
# Automatic cost calculation
watch.log_llm_call(
    model="claude-3-opus",
    input_tokens=1500,
    output_tokens=3000,
    # Cost calculated automatically from model pricing
)

# Or manual cost
watch.log_cost(amount=0.15, currency="USD", category="llm")
```

### Compliance Events

```python
# Log compliance-relevant events
watch.log_compliance_event(
    event_type="data_access",
    resource="customer_pii",
    action="read",
    justification="Customer requested account summary",
    data_classification="confidential"
)
```

### Policy Enforcement

```python
# Define policies
watch.set_policy("max_cost_per_task", 1.00)  # $1 max
watch.set_policy("allowed_tools", ["search", "calculator"])
watch.set_policy("pii_handling", "redact")

# Check before execution
if watch.check_policy("cost_budget"):
    agent.run()
else:
    watch.alert("Budget exceeded", severity="high")
```

---

## Dashboard Features

### Real-time Activity Feed
Live stream of all agent actions across your deployment.

### Cost Analytics
- Cost per agent, per customer, per task type
- Trend analysis and forecasting
- Budget alerts and caps

### Compliance Center
- Auto-generated audit trails
- SOC2 evidence collection
- Data access logs
- Policy violation reports

### Performance Metrics
- Success/failure rates
- Latency percentiles (p50, p95, p99)
- Throughput over time
- Error categorization

### Anomaly Detection
- Unusual cost spikes
- Behavior deviation from baseline
- Failed task patterns
- Security alerts

---

## Pricing (Planned)

| Tier | Price | Events/mo | Features |
|------|-------|-----------|----------|
| **Free** | $0 | 10K | Basic monitoring, 7-day retention |
| **Pro** | $99/mo | 1M | Full analytics, 90-day retention, alerts |
| **Enterprise** | Custom | Unlimited | Compliance suite, SSO, dedicated support |

---

## Roadmap

### MVP (Current)
- [x] Event ingestion API
- [x] Real-time dashboard
- [x] Cost tracking
- [x] Basic compliance logging
- [x] Python SDK

### v1.0
- [ ] Anomaly detection ML model
- [ ] Slack/PagerDuty integrations
- [ ] SOC2 report generator
- [ ] Multi-tenant architecture

### v2.0
- [ ] JavaScript/TypeScript SDK
- [ ] LangChain native integration
- [ ] Custom policy DSL
- [ ] Self-hosted option

---

## Why This Matters

The AI agent market is exploding. But enterprises won't deploy agents without:

1. **Visibility** - "What are these agents doing?"
2. **Control** - "Can we stop them if needed?"
3. **Compliance** - "Can we prove they behaved?"
4. **Economics** - "What's the ROI?"

**AgentWatch answers all four.** We're the trust layer that unlocks enterprise AI agent adoption.

---

## Contributing

This is an MVP. Contributions welcome:

1. Fork the repo
2. Create a feature branch
3. Submit a PR

---

## License

MIT License - see [LICENSE](LICENSE)

---

## Contact

Built by [Jamey's AI Agent Business]

**Let's make AI agents trustworthy at scale.**
