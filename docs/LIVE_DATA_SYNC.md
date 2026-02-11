# AgentWatch Live Data Sync (OpenClaw Integration)

Connects AgentWatch dashboard to **real OpenClaw agent activity** (replaces demo data).

## How It Works

1. **Polling Daemon** runs continuously
2. Fetches `sessions_list` from OpenClaw every 30s
3. Filters with **code-only logic** (no LLM calls)
4. Maps sessions → telemetry events
5. Posts to AgentWatch API
6. Dashboard shows **live agent activity**

## Architecture

```
OpenClaw Gateway (http://127.0.0.1:18789)
        ↓
  sessions_list API
        ↓
  PollingDaemon (zero-LLM)
        ├─ OpenClawClient (fetch)
        ├─ DataMapper (pure Python filter/transform)
        └─ AgentWatch API (push)
        ↓
  AgentWatch Dashboard
        ↓
  Real-time agent visibility
```

## Getting Started

### 1. Start AgentWatch (if not already running)

```bash
python run.py
```

This starts:
- API: http://localhost:8765
- Dashboard: http://localhost:8766

### 2. Start the Syncer (in a separate terminal)

```bash
python start_syncer.py
```

Output:
```
2026-02-10 20:30:45 [INFO] - Starting OpenClaw→AgentWatch polling daemon
2026-02-10 20:30:45 [INFO] -   Poll interval: 30s
2026-02-10 20:30:45 [INFO] -   OpenClaw URL: http://127.0.0.1:18789
2026-02-10 20:30:45 [INFO] -   AgentWatch URL: http://localhost:8765
2026-02-10 20:30:46 [INFO] - ✓ Ingested 3 events (total: 3)
2026-02-10 20:31:16 [INFO] - Poll #2: 5 sessions → 2 events (0.45s)
```

### 3. Verify in Dashboard

Open http://localhost:8766:
- **Activity Feed** should show real agents from OpenClaw
- **Cost Analytics** populated with actual token usage
- **Agent Performance** charts with live data

## Configuration

### Programmatic

```python
from src.integrations.polling_daemon import PollingDaemon

daemon = PollingDaemon(
    openclaw_url="http://127.0.0.1:18789",  # OpenClaw gateway
    agentwatch_url="http://localhost:8765",  # AgentWatch API
    poll_interval_s=30,                      # Poll every 30s
    batch_size=50,                           # Max sessions per poll
    max_errors=10,                           # Stop after 10 errors
)
daemon.run()
```

### CLI

```bash
python -m src.integrations.polling_daemon \
  --openclaw-url http://127.0.0.1:18789 \
  --agentwatch-url http://localhost:8765 \
  --poll-interval 30 \
  --log-level INFO
```

### Run Once (Testing)

```bash
python -m src.integrations.polling_daemon --once
```

Fetches one batch of sessions and exits.

## Cost Profile

**Zero LLM costs during polling.** Here's why:

- ✅ Uses code-based filtering (Python `if` statements)
- ✅ No Claude/GPT calls in the loop
- ✅ Simple token counting + math
- ✅ Fast (~0.5s per poll)

**Only costs:** OpenClaw gateway API calls (local HTTP, free)

## What Gets Ingested

The syncer filters for:

| Session Type | Ingested? | Reason |
|--------------|-----------|--------|
| `main` | ✅ Yes | User-initiated agent |
| `subagent` | ✅ Yes | Sub-task execution |
| `group` | ✅ Yes | Multi-user sessions |
| `cron` | ❌ No | Internal monitoring (noise) |

Other filters:
- Only sessions active in last 30 minutes
- Skip sessions with <10 total tokens (noise)
- Deduplicate by session ID

## What Gets Mapped

Each session becomes a **Telemetry Event** with:

```json
{
  "agent_name": "gh-taskmaster-22",
  "agent_id": "haiku",
  "event_type": "execution",
  "trace_id": "uuid",
  "session_id": "...",
  "input_tokens": 600,
  "output_tokens": 400,
  "model": "claude-haiku-4-5",
  "status": "running",
  "metadata": {
    "kind": "subagent",
    "label": "gh-taskmaster:22",
    "channel": "github",
    "context_used_pct": 35
  },
  "timestamp": "2026-02-10T20:31:15Z"
}
```

## Monitoring the Syncer

### Check Logs

```bash
# Tail the syncer output
tail -f agentwatch.log  # (if configured)

# Or just watch stdout
# (daemon prints to console)
```

### Expected Behavior

- **First poll:** "Poll #1: 15 sessions → 8 events"
- **Idle periods:** "Poll #X: 0 sessions → 0 events"
- **Errors:** Retries up to 10 times, then stops

### Health Check

Hit the dashboard and verify:
1. New agents appear in the activity feed
2. Cost data matches OpenClaw usage
3. No error alerts on dashboard

## Troubleshooting

### "Connection refused" to OpenClaw

**Problem:** `http://127.0.0.1:18789` not reachable

**Solution:**
```bash
# Verify OpenClaw gateway is running
openclaw gateway status

# If not, start it
openclaw gateway start

# Change URL if running elsewhere
python start_syncer.py --openclaw-url http://your-gateway-url:18789
```

### "Connection refused" to AgentWatch

**Problem:** AgentWatch API not running on localhost:8765

**Solution:**
```bash
# Start AgentWatch
python run.py

# Or specify different URL
python start_syncer.py --agentwatch-url http://your-agentwatch-url:8765
```

### No events appearing in dashboard

**Possible causes:**
1. No active agents in OpenClaw (spawn a sub-agent first)
2. Syncer is filtering out sessions (check logs)
3. API push is failing (check error logs)

**Debug:**
```bash
python -m src.integrations.polling_daemon --log-level DEBUG --once
```

This shows detailed filtering decisions.

### High CPU/Memory usage

**Solution:** Reduce poll frequency
```python
daemon = PollingDaemon(poll_interval_s=60)  # Poll every 60s instead of 30s
```

## Cost Estimation

**For your setup:**

- **OpenClaw calls:** ~2/minute → free (local HTTP)
- **AgentWatch ingestion:** ~$0.0001/1000 events (negligible)
- **Bandwidth:** <100KB/minute

**Total monthly cost:** **~$0.00** (polling only)

The LLM costs come from the agents themselves, not the monitoring.

## API Endpoints Used

The syncer calls:

1. **OpenClaw:**
   - `GET /api/sessions` — Fetch active sessions (free, local)

2. **AgentWatch:**
   - `POST /api/events/bulk` — Ingest telemetry events

## Roadmap

- [ ] Kubernetes deployment (Helm chart)
- [ ] Prometheus metrics export
- [ ] Custom filter DSL (SQL-like)
- [ ] Webhook alerts (Slack, PagerDuty)
- [ ] Historical data backfill

## Questions?

See the main [README.md](../README.md) for platform documentation.
