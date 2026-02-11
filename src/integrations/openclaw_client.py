"""
OpenClaw Session File Reader

Lightweight reader for OpenClaw session JSONL files.
Zero LLM costs — pure filesystem reads + Python filtering.
Reads session files directly from ~/.openclaw/agents/<agentId>/sessions/*.jsonl
"""

import os
import json
from datetime import datetime, timedelta, timezone
from typing import List, Dict, Any, Optional
from pathlib import Path
from dataclasses import dataclass


@dataclass
class SessionTelemetry:
    """Extracted telemetry from an OpenClaw session."""
    session_id: str
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
    Reads OpenClaw session JSONL files directly from filesystem.
    No API, no CLI — just file reads. Zero overhead.
    """
    
    def __init__(self, openclaw_home: Optional[str] = None):
        # Default to ~/.openclaw
        if openclaw_home:
            self.openclaw_home = Path(openclaw_home).expanduser()
        else:
            self.openclaw_home = Path.home() / ".openclaw"
        
        self.sessions_dir = self.openclaw_home / "agents"
        
        if not self.sessions_dir.exists():
            raise OpenClawError(f"OpenClaw directory not found: {self.sessions_dir}")
    
    def get_sessions(self, 
                     kinds: Optional[List[str]] = None,
                     limit: int = 50,
                     active_minutes: Optional[int] = None) -> List[Dict[str, Any]]:
        """
        Read active sessions from OpenClaw JSONL files on disk.
        
        Scans ~/.openclaw/agents/*/sessions/*.jsonl for active sessions.
        No API, no CLI — pure filesystem reads.
        
        Args:
            kinds: Filter by session kind (main, subagent, cron, group)
            limit: Max results
            active_minutes: Only sessions active in last N minutes
        
        Returns:
            List of session dicts with metadata
        
        Raises:
            OpenClawError: If sessions directory not found
        """
        sessions = []
        cutoff_time = None
        
        if active_minutes:
            cutoff_time = datetime.now(timezone.utc) - timedelta(minutes=active_minutes)
        
        # Scan all agent directories
        try:
            for agent_dir in self.sessions_dir.iterdir():
                if not agent_dir.is_dir():
                    continue
                
                agent_id = agent_dir.name
                sessions_subdir = agent_dir / "sessions"
                
                if not sessions_subdir.exists():
                    continue
                
                # Read all JSONL files in this agent's sessions directory
                for session_file in sorted(sessions_subdir.glob("*.jsonl"), reverse=True):
                    if len(sessions) >= limit:
                        break
                    
                    session_data = self._parse_session_file(
                        session_file, agent_id, cutoff_time
                    )
                    
                    if session_data:
                        # Filter by kind if specified
                        if kinds and session_data.get("kind") not in kinds:
                            continue
                        
                        sessions.append(session_data)
        except Exception as e:
            raise OpenClawError(f"Failed to scan sessions: {e}")
        
        return sessions[:limit]
    
    def _parse_session_file(self, 
                           filepath: Path, 
                           agent_id: str,
                           cutoff_time: Optional[datetime] = None) -> Optional[Dict[str, Any]]:
        """
        Parse a single JSONL session file.
        Extract metadata: agent ID, model, token counts, timestamps.
        """
        try:
            # Read last few lines (most recent state)
            lines = []
            with open(filepath, 'r', encoding='utf-8', errors='ignore') as f:
                # Read entire file to get latest state
                for line in f:
                    if line.strip():
                        lines.append(line)
            
            if not lines:
                return None
            
            # Try to find metadata in recent messages
            total_tokens = 0
            context_tokens = 0
            model = "unknown"
            last_timestamp = None
            kind = "unknown"
            channel = "unknown"
            
            # Scan backwards through file for token counts and metadata
            for line in reversed(lines[-10:]):  # Check last 10 lines
                try:
                    obj = json.loads(line)
                    
                    # Look for token counts
                    if "totalTokens" in obj:
                        total_tokens = obj.get("totalTokens", 0)
                    if "contextTokens" in obj:
                        context_tokens = obj.get("contextTokens", 0)
                    if "model" in obj:
                        model = obj.get("model", "unknown")
                    if "kind" in obj:
                        kind = obj.get("kind", "unknown")
                    if "channel" in obj:
                        channel = obj.get("channel", "unknown")
                    if "timestamp" in obj:
                        last_timestamp = obj.get("timestamp")
                    
                    # If we found key fields, we can stop
                    if total_tokens > 0 and model != "unknown":
                        break
                except json.JSONDecodeError:
                    pass
            
            # Get file modification time as fallback
            mtime = filepath.stat().st_mtime * 1000  # Convert to ms
            
            # Check if session is recent enough
            if cutoff_time and last_timestamp:
                try:
                    ts = datetime.fromisoformat(last_timestamp)
                    if ts < cutoff_time:
                        return None
                except:
                    pass
            
            return {
                "sessionId": filepath.stem,
                "agentId": agent_id,
                "kind": kind,
                "label": None,
                "totalTokens": total_tokens,
                "contextTokens": context_tokens,
                "model": model,
                "channel": channel,
                "updatedAt": int(mtime),
                "lastMessageTimestamp": last_timestamp,
            }
        
        except Exception as e:
            return None
    
    def extract_telemetry(self, session: Dict[str, Any]) -> SessionTelemetry:
        """Map raw session to telemetry. Pure Python — no LLM calls."""
        return SessionTelemetry(
            session_id=session.get("sessionId", ""),
            agent_id=session.get("agentId", "unknown"),
            kind=session.get("kind", "unknown"),
            label=session.get("label"),
            status=self._infer_status(session),
            total_tokens=session.get("totalTokens", 0),
            context_tokens=session.get("contextTokens", 0),
            updated_at_ms=session.get("updatedAt", 0),
            model=session.get("model", "unknown"),
            last_message_timestamp=session.get("lastMessageTimestamp"),
            channel=session.get("channel", "unknown"),
        )
    
    @staticmethod
    def _infer_status(session: Dict[str, Any]) -> str:
        """Infer status from session fields (code-only, no LLM)."""
        # For file-based reader, we don't have abort status, assume active
        return "active"
    
    def close(self):
        """No-op for file-based reader."""
        pass


class OpenClawError(Exception):
    """Error from OpenClaw client."""
    pass
