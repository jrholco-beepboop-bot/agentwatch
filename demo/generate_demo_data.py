"""
AgentWatch Demo Data Generator

Generates realistic demo data to showcase the platform.
Run this after starting the API server.
"""

import asyncio
import random
import uuid
from datetime import datetime, timedelta
import httpx

API_URL = "http://localhost:8765"

# Demo agents
AGENTS = [
    {"name": "Customer Support Agent", "type": "support", "owner": "Support Team"},
    {"name": "Sales Outreach Agent", "type": "sales", "owner": "Sales Team"},
    {"name": "Document Processor", "type": "operations", "owner": "Ops Team"},
    {"name": "Research Assistant", "type": "research", "owner": "Product Team"},
    {"name": "Code Review Agent", "type": "engineering", "owner": "Engineering"},
]

# Task types per agent
TASK_TYPES = {
    "Customer Support Agent": ["ticket_response", "faq_answer", "escalation_check", "sentiment_analysis"],
    "Sales Outreach Agent": ["lead_qualification", "email_draft", "follow_up", "proposal_generation"],
    "Document Processor": ["contract_analysis", "data_extraction", "summarization", "classification"],
    "Research Assistant": ["market_research", "competitor_analysis", "trend_report", "fact_check"],
    "Code Review Agent": ["pr_review", "security_scan", "style_check", "documentation_check"],
}

# Models used
MODELS = [
    ("claude-3-5-sonnet", 0.7),
    ("claude-3-haiku", 0.2),
    ("gpt-4o", 0.08),
    ("gpt-3.5-turbo", 0.02),
]


def weighted_choice(choices):
    """Pick from weighted choices."""
    items, weights = zip(*choices)
    return random.choices(items, weights=weights)[0]


async def create_agent(client: httpx.AsyncClient, agent_data: dict) -> str:
    """Create an agent and return its ID."""
    response = await client.post(
        f"{API_URL}/api/agents",
        json={
            "name": agent_data["name"],
            "description": f"Demo {agent_data['type']} agent",
            "agent_type": agent_data["type"],
            "owner": agent_data["owner"],
            "config": {"demo": True}
        }
    )
    if response.status_code == 200:
        return response.json()["id"]
    return str(uuid.uuid4())


async def create_trace(client: httpx.AsyncClient, agent_id: str, agent_name: str) -> dict:
    """Create a trace with events and costs."""
    task_type = random.choice(TASK_TYPES.get(agent_name, ["general_task"]))
    user_id = f"user_{random.randint(100, 999)}"
    
    # Determine outcome (90% success for demo)
    is_success = random.random() < 0.90
    status = "success" if is_success else random.choice(["error", "timeout"])
    
    # Create trace
    response = await client.post(
        f"{API_URL}/api/traces",
        json={
            "agent_id": agent_id,
            "environment": random.choice(["production", "production", "production", "staging"]),
            "user_id": user_id,
            "session_id": f"session_{uuid.uuid4().hex[:8]}",
            "task_type": task_type,
            "input_summary": f"Process {task_type.replace('_', ' ')} request",
            "attributes": {"priority": random.choice(["low", "medium", "high"])}
        }
    )
    
    if response.status_code != 200:
        return None
    
    trace = response.json()
    trace_id = trace["id"]
    
    # Generate LLM calls (1-3 per trace)
    num_llm_calls = random.randint(1, 3)
    total_cost = 0
    
    for i in range(num_llm_calls):
        model = weighted_choice(MODELS)
        input_tokens = random.randint(100, 2000)
        output_tokens = random.randint(50, 1500)
        duration = random.randint(500, 5000)
        
        await client.post(
            f"{API_URL}/api/events",
            json={
                "trace_id": trace_id,
                "event_type": "llm_call",
                "event_name": f"LLM Call {i+1}",
                "model": model,
                "input_tokens": input_tokens,
                "output_tokens": output_tokens,
                "duration_ms": duration,
                "status": "success" if is_success or i < num_llm_calls - 1 else "error"
            }
        )
    
    # Maybe add tool calls
    if random.random() < 0.4:
        tools = ["web_search", "database_query", "file_read", "api_call", "calculator"]
        for _ in range(random.randint(1, 2)):
            await client.post(
                f"{API_URL}/api/events",
                json={
                    "trace_id": trace_id,
                    "event_type": "tool_call",
                    "event_name": random.choice(tools),
                    "duration_ms": random.randint(50, 500),
                    "status": "success"
                }
            )
    
    # Add compliance event for sensitive operations
    if random.random() < 0.3:
        await client.post(
            f"{API_URL}/api/compliance",
            json={
                "trace_id": trace_id,
                "event_type": random.choice(["data_access", "pii_handling", "external_call"]),
                "action": random.choice(["read", "process", "transmit"]),
                "resource": random.choice(["customer_data", "financial_records", "user_profile"]),
                "data_classification": random.choice(["internal", "confidential"]),
                "justification": "Required for task completion",
                "outcome": "allowed"
            }
        )
    
    # Complete the trace
    duration = random.randint(1000, 15000) if is_success else random.randint(500, 30000)
    await client.patch(
        f"{API_URL}/api/traces/{trace_id}",
        json={
            "status": status,
            "error_message": "Timeout exceeded" if status == "timeout" else ("API error" if status == "error" else None),
            "output_summary": "Task completed successfully" if is_success else "Task failed"
        }
    )
    
    return trace


async def create_alert(client: httpx.AsyncClient, agent_ids: list):
    """Create some demo alerts."""
    alerts = [
        {"title": "High error rate detected", "severity": "error", "alert_type": "error_spike", "description": "Error rate exceeded 10% threshold"},
        {"title": "Cost spike warning", "severity": "warning", "alert_type": "cost_spike", "description": "Hourly cost 50% above baseline"},
        {"title": "Unusual activity pattern", "severity": "info", "alert_type": "anomaly", "description": "Agent behavior deviation detected"},
    ]
    
    for alert in random.sample(alerts, k=random.randint(1, len(alerts))):
        alert["agent_id"] = random.choice(agent_ids)
        await client.post(f"{API_URL}/api/alerts", json=alert)


async def main():
    """Generate demo data."""
    print("AgentWatch Demo Data Generator")
    print("=" * 50)
    
    async with httpx.AsyncClient(timeout=30.0) as client:
        # Check API is running
        try:
            response = await client.get(f"{API_URL}/health")
            if response.status_code != 200:
                print("[ERROR] API not responding. Start it with: python -m src.api.main")
                return
        except Exception as e:
            print(f"[ERROR] Cannot connect to API at {API_URL}")
            print("        Start the API with: python -m src.api.main")
            return
        
        print("[OK] API is running")
        
        # Create agents
        print("\nCreating agents...")
        agent_ids = {}
        for agent in AGENTS:
            agent_id = await create_agent(client, agent)
            agent_ids[agent["name"]] = agent_id
            print(f"   [+] {agent['name']}")
        
        # Generate traces (simulate last 7 days of activity)
        print("\nGenerating traces...")
        total_traces = 0
        
        for hours_ago in range(168, 0, -1):  # Last 7 days, hourly
            # Generate 0-5 traces per hour per agent
            for agent_name, agent_id in agent_ids.items():
                num_traces = random.randint(0, 5)
                for _ in range(num_traces):
                    await create_trace(client, agent_id, agent_name)
                    total_traces += 1
            
            if hours_ago % 24 == 0:
                print(f"   Day -{hours_ago // 24}: {total_traces} traces generated")
        
        print(f"   [OK] Total: {total_traces} traces")
        
        # Create some alerts
        print("\nCreating sample alerts...")
        await create_alert(client, list(agent_ids.values()))
        print("   [OK] Alerts created")
        
        print("\n" + "=" * 50)
        print("[DONE] Demo data generation complete!")
        print("\nView the dashboard at: http://localhost:8766")
        print("API docs at: http://localhost:8765/docs")


if __name__ == "__main__":
    asyncio.run(main())
