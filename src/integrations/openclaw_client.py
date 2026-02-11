"""
OpenClaw API Client

Lightweight wrapper for OpenClaw sessions_list polling.
Zero LLM costs — pure Python filtering only.
"""

import os
import json
from datetime import datetime
from typing import List, Dict, Any, Optional
import httpx
from dataclasses import dataclass


@dataclass
class SessionTelemetry:
    """Extracted telemetry from an OpenClaw session."""
    session_id: str
    session_key: str
    agent_id: str
    kind: str  # "main", "subagent", "cron", "group"
    label: Optional[str]
    status: str  # "active", "completed", "error"
    total_tokens: int
    context_tokens: int
    updated_at_ms: int
    model: str
    last_message_timestamp: Optional[int]
    channel: str


class OpenClawClient:
    """
    Non-blocking, zero-LLM client for OpenClaw monitoring.
    Calls sessions_list endpoint only — no analysis.
    """
    
    def __init__(self, api_url: str = "http://127.0.0.1:18789", timeout_s: int = 5):
        self.api_url = api_url.rstrip("/")
        self.timeout = timeout_s
        self.client = httpx.Client(timeout=timeout_s)
    
    def get_sessions(self, 
                     kinds: Optional[List[str]] = None,
                     limit: int = 50,
                     active_minutes: Optional[int] = None) -> List[Dict[str, Any]]:
        """
        Fetch raw sessions from OpenClaw via HTTP API or CLI fallback.
        
        Tries gateway HTTP API first, falls back to CLI if needed.
        
        Args:
            kinds: Filter by session kind (main, subagent, cron, group)
            limit: Max results
            active_minutes: Only sessions active in last N minutes
        
        Returns:
            List of session objects
        
        Raises:
            OpenClawError: If both API and CLI fail
        """
        import subprocess
        
        # Try HTTP API first
        try:
            params = {"limit": limit}
            if kinds:
                params["kinds"] = ",".join(kinds)
            if active_minutes:
                params["activeMinutes"] = active_minutes
            
            resp = self.client.get(f"{self.api_url}/api/sessions", params=params, timeout=5)
            
            if resp.status_code == 200:
                try:
                    data = resp.json()
                    if isinstance(data, list):
                        return data
                    elif isinstance(data, dict) and "sessions" in data:
                        return data["sessions"]
                    else:
                        return data if isinstance(data, list) else []
                except (json.JSONDecodeError, ValueError):
                    # Response isn't JSON, might be HTML or text
                    pass
        except Exception:
            pass  # Fall through to CLI
        
        # Fallback to CLI
        try:
            cmd = ["openclaw", "sessions", "list", f"--limit={limit}"]
            if kinds:
                cmd.append(f"--kinds={','.join(kinds)}")
            if active_minutes:
                cmd.append(f"--activeMinutes={active_minutes}")
            
            result = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                timeout=10
            )
            
            if result.returncode != 0:
                raise OpenClawError(f"openclaw command failed: {result.stderr}")
            
            # Parse JSON output
            data = json.loads(result.stdout)
            
            # Response is either a list directly or wrapped in a dict
            if isinstance(data, list):
                return data
            elif isinstance(data, dict) and "sessions" in data:
                return data["sessions"]
            else:
                return data if isinstance(data, list) else []
        
        except json.JSONDecodeError as e:
            raise OpenClawError(f"Invalid response JSON: {e}")
        except subprocess.TimeoutExpired:
            raise OpenClawError("OpenClaw command timed out")
        except FileNotFoundError:
            raise OpenClawError("openclaw CLI not found in PATH")
    
    def extract_telemetry(self, session: Dict[str, Any]) -> SessionTelemetry:
        """
        Map raw session to telemetry.
        Pure Python — no LLM calls.
        """
        return SessionTelemetry(
            session_id=session.get("sessionId", ""),
            session_key=session.get("key", ""),
            agent_id=session.get("agentId", "unknown"),
            kind=session.get("kind", "unknown"),
            label=session.get("label"),
            status=self._infer_status(session),
            total_tokens=session.get("totalTokens", 0),
            context_tokens=session.get("contextTokens", 0),
            updated_at_ms=session.get("updatedAt", 0),
            model=session.get("model", "unknown"),
            last_message_timestamp=session.get("messages", [{}])[-1].get("timestamp"),
            channel=session.get("channel", "unknown"),
        )
    
    @staticmethod
    def _infer_status(session: Dict[str, Any]) -> str:
        """Infer status from session fields (code-only, no LLM)."""
        if session.get("abortedLastRun"):
            return "error"
        messages = session.get("messages", [])
        if messages and messages[-1].get("role") == "assistant":
            return "completed"
        return "active"
    
    def close(self):
        """Clean up HTTP client."""
        self.client.close()


class OpenClawError(Exception):
    """Error from OpenClaw client."""
    pass
