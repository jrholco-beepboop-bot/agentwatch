"""
Example: Instrumenting an Agent with AgentWatch

This shows how easy it is to add observability to any AI agent.
"""

import sys
import os
import time
import random

# Add parent directory to path for imports
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from src.sdk import AgentWatch


def simulate_llm_call(prompt: str) -> tuple[str, int, int]:
    """Simulate an LLM API call."""
    time.sleep(random.uniform(0.5, 2.0))  # Simulate latency
    input_tokens = len(prompt.split()) * 2  # Rough estimate
    output_tokens = random.randint(50, 300)
    response = f"Simulated response to: {prompt[:50]}..."
    return response, input_tokens, output_tokens


def simulate_tool_call(tool_name: str) -> dict:
    """Simulate a tool call."""
    time.sleep(random.uniform(0.1, 0.5))
    return {"tool": tool_name, "result": "success", "data": {"example": True}}


class MyCustomerSupportAgent:
    """Example customer support agent with AgentWatch instrumentation."""
    
    def __init__(self):
        # Initialize AgentWatch (uses localhost by default)
        self.watch = AgentWatch(
            api_url="http://localhost:8765",
            environment="development"
        )
    
    def handle_ticket(self, ticket_id: str, customer_id: str, message: str) -> str:
        """Handle a customer support ticket."""
        
        # Wrap the entire operation in a trace
        with self.watch.trace(
            "Customer Support Agent",
            user_id=customer_id,
            task_type="ticket_response"
        ) as span:
            
            # Set input summary (truncated for privacy)
            span.set_input(f"Ticket {ticket_id}: {message[:100]}")
            span.set_attribute("ticket_id", ticket_id)
            span.set_attribute("priority", "medium")
            
            try:
                # Step 1: Analyze the message
                analysis_prompt = f"Analyze customer intent: {message}"
                _, input_tok, output_tok = simulate_llm_call(analysis_prompt)
                span.log_llm_call(
                    model="claude-3-5-sonnet",
                    input_tokens=input_tok,
                    output_tokens=output_tok,
                    duration_ms=1500
                )
                
                # Step 2: Search knowledge base (tool call)
                kb_result = simulate_tool_call("knowledge_base_search")
                span.log_tool_call(
                    tool_name="knowledge_base_search",
                    input_data={"query": message[:50]},
                    output_data=kb_result,
                    duration_ms=200
                )
                
                # Step 3: Check if PII handling needed (compliance event)
                if "account" in message.lower() or "personal" in message.lower():
                    span.log_compliance_event(
                        event_type="pii_handling",
                        action="access",
                        resource="customer_profile",
                        justification="Required to answer customer query about their account",
                        data_classification="confidential",
                        outcome="allowed"
                    )
                
                # Step 4: Generate response
                response_prompt = f"Generate helpful response for: {message}"
                response, input_tok, output_tok = simulate_llm_call(response_prompt)
                span.log_llm_call(
                    model="claude-3-5-sonnet",
                    input_tokens=input_tok,
                    output_tokens=output_tok,
                    duration_ms=2000
                )
                
                # Mark success
                span.set_output(response)
                span.set_status("success")
                
                print(f"✓ Ticket {ticket_id} handled successfully")
                return response
                
            except Exception as e:
                # Errors are automatically captured
                span.set_status("error", str(e))
                print(f"✗ Error handling ticket {ticket_id}: {e}")
                raise


def main():
    """Run the example agent."""
    print("=" * 60)
    print("AgentWatch SDK Example - Customer Support Agent")
    print("=" * 60)
    print("\nMake sure the API is running: python -m src.api.main")
    print()
    
    agent = MyCustomerSupportAgent()
    
    # Simulate handling several tickets
    tickets = [
        ("TKT-001", "cust-123", "I can't log into my account, it says password incorrect"),
        ("TKT-002", "cust-456", "What are your business hours?"),
        ("TKT-003", "cust-789", "I want to cancel my subscription"),
        ("TKT-004", "cust-321", "How do I export my personal data?"),
        ("TKT-005", "cust-654", "Your product is great, just wanted to say thanks!"),
    ]
    
    for ticket_id, customer_id, message in tickets:
        print(f"\n📨 Processing {ticket_id}...")
        try:
            agent.handle_ticket(ticket_id, customer_id, message)
        except Exception as e:
            print(f"   Failed: {e}")
    
    print("\n" + "=" * 60)
    print("✅ Done! Check the dashboard at http://localhost:8766")
    print("=" * 60)


if __name__ == "__main__":
    main()
