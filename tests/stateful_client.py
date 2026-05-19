"""
Stateful LM Studio Client for Python Services

Uses the LM Studio 0.4.0 /v1/responses endpoint with previous_response_id
for KV cache reuse, dramatically improving prompt processing speed.

Usage:
    from stateful_client import get_stateful_client

    client = get_stateful_client()
    response = client.chat(
        conversation_id="session_abc123",
        messages=[{"role": "user", "content": "Hello"}]
    )
"""

import os
import re
import time
import json
import requests
from threading import Lock
from typing import Dict, List, Optional, Any
from dataclasses import dataclass
from datetime import datetime


def _strip_thinking(text):
    """Strip <think>...</think> blocks and 'Thinking Process:...' preambles from model output."""
    text = re.sub(r'<think>.*?</think>', '', text, flags=re.DOTALL).strip()
    text = re.sub(r'<think>.*$', '', text, flags=re.DOTALL).strip()
    text = re.sub(r'^Thinking Process:.*?(?=\n\n[A-Z{"\[])', '', text, flags=re.DOTALL).strip()
    if text.startswith('Thinking Process:'):
        text = ''
    return text


@dataclass
class ResponseEntry:
    """Stores response ID with metadata"""
    response_id: str
    model: str
    timestamp: float
    access_count: int = 0


class ResponseIDStorage:
    """
    Thread-safe storage for response IDs with TTL.

    Stores response IDs per conversation to enable KV cache reuse
    via the /v1/responses endpoint's previous_response_id parameter.
    """

    def __init__(self, ttl_seconds: int = 600):
        """
        Args:
            ttl_seconds: Time-to-live in seconds (default: 10 minutes)
        """
        self.store: Dict[str, ResponseEntry] = {}
        self.ttl = ttl_seconds
        self.lock = Lock()

        print(f"[ResponseStorage] Initialized with TTL: {ttl_seconds}s")

    def set(self, conversation_id: str, response_id: str, model: str = None) -> None:
        """Store a response ID for a conversation"""
        if not conversation_id or not response_id:
            return

        with self.lock:
            self.store[conversation_id] = ResponseEntry(
                response_id=response_id,
                model=model or "",
                timestamp=time.time()
            )

        print(f"[ResponseStorage] Stored {response_id} for {conversation_id}")

    def get(self, conversation_id: str) -> Optional[str]:
        """Get response ID for a conversation, returns None if expired"""
        with self.lock:
            entry = self.store.get(conversation_id)

            if not entry:
                return None

            # Check TTL
            age = time.time() - entry.timestamp
            if age > self.ttl:
                print(f"[ResponseStorage] Entry expired for {conversation_id} (age: {age:.0f}s)")
                del self.store[conversation_id]
                return None

            # Update access timestamp and count
            entry.timestamp = time.time()
            entry.access_count += 1

            return entry.response_id

    def get_entry(self, conversation_id: str) -> Optional[ResponseEntry]:
        """Get full entry with metadata"""
        with self.lock:
            entry = self.store.get(conversation_id)
            if not entry:
                return None

            age = time.time() - entry.timestamp
            if age > self.ttl:
                del self.store[conversation_id]
                return None

            return entry

    def has_model_changed(self, conversation_id: str, current_model: str) -> bool:
        """Check if model changed since last request"""
        with self.lock:
            entry = self.store.get(conversation_id)
            if not entry or not entry.model:
                return False
            return entry.model != current_model

    def delete(self, conversation_id: str) -> None:
        """Delete a conversation's response ID"""
        with self.lock:
            if conversation_id in self.store:
                del self.store[conversation_id]
                print(f"[ResponseStorage] Deleted entry for {conversation_id}")

    def clear(self) -> None:
        """Clear all stored response IDs"""
        with self.lock:
            count = len(self.store)
            self.store.clear()
            print(f"[ResponseStorage] Cleared all {count} entries")

    def cleanup(self) -> int:
        """Remove expired entries, returns count of removed entries"""
        now = time.time()
        expired = 0

        with self.lock:
            to_delete = [
                cid for cid, entry in self.store.items()
                if now - entry.timestamp > self.ttl
            ]
            for cid in to_delete:
                del self.store[cid]
                expired += 1

        if expired > 0:
            print(f"[ResponseStorage] Cleanup removed {expired} expired entries")

        return expired

    def get_stats(self) -> Dict[str, Any]:
        """Get storage statistics"""
        with self.lock:
            now = time.time()
            total_access = sum(e.access_count for e in self.store.values())
            oldest_age = max(
                (now - e.timestamp for e in self.store.values()),
                default=0
            )

            return {
                "size": len(self.store),
                "ttl_seconds": self.ttl,
                "total_access_count": total_access,
                "oldest_age_seconds": oldest_age
            }


class StatefulLMStudioClient:
    """
    Stateful client for LM Studio 0.4.0+ /v1/responses API.

    Uses previous_response_id to chain conversations and reuse KV cache.
    """

    def __init__(
        self,
        base_url: str = None,
        timeout: int = 300,
        max_retries: int = 2,
        ttl_seconds: int = 600
    ):
        """
        Args:
            base_url: LM Studio API base URL (e.g., http://localhost:1234)
            timeout: Request timeout in seconds
            max_retries: Max retries on transient failures
            ttl_seconds: TTL for response ID storage
        """
        self.base_url = base_url or os.environ.get(
            "LM_STUDIO_API_BASE",
            "http://localhost:1234"  # Direct to LM Studio API (Windows host IP)
        ).rstrip("/")
        self.timeout = timeout
        self.max_retries = max_retries
        self.storage = ResponseIDStorage(ttl_seconds=ttl_seconds)

        print(f"[StatefulClient] Initialized with base_url: {self.base_url}")

    def chat(
        self,
        conversation_id: str,
        messages: List[Dict[str, str]],
        model: str = None,
        max_tokens: int = 2048,
        temperature: float = 0.1,
        tools: List[Dict] = None,
        full_history: List[Dict] = None
    ) -> Dict[str, Any]:
        """
        Send a chat message using stateful API with KV cache reuse.

        Args:
            conversation_id: Unique conversation ID (e.g., session_abc123)
            messages: Array of message dicts [{"role": "user", "content": "..."}]
            model: Model ID to use
            max_tokens: Max tokens to generate
            temperature: Sampling temperature (0-2)
            tools: Tool definitions for function calling
            full_history: Full message history for fallback

        Returns:
            Dict with: response, responseId, usedStateful, usage
        """
        try:
            from chat_server import get_active_model
            model = model or get_active_model()
        except ImportError:
            model = model or os.environ.get("LM_STUDIO_MODEL", "nemotron-cascade-2-30b-a3b")

        # Check if model changed since last request
        if self.storage.has_model_changed(conversation_id, model):
            print(f"[StatefulClient] Model changed for {conversation_id}, clearing response ID")
            self.storage.delete(conversation_id)

        # Get previous response ID for KV cache reuse
        previous_response_id = self.storage.get(conversation_id)

        # Try stateful API
        if previous_response_id:
            try:
                result = self._call_stateful_api(
                    messages, previous_response_id, model,
                    max_tokens, temperature, tools
                )
                # Update stored response ID
                if result.get("responseId"):
                    self.storage.set(conversation_id, result["responseId"], model)
                return result
            except Exception as e:
                print(f"[StatefulClient] Stateful request failed, falling back: {e}")
                self.storage.delete(conversation_id)

        # Try stateful API without previous_response_id (new conversation)
        try:
            result = self._call_stateful_api(
                messages, None, model,
                max_tokens, temperature, tools
            )
            # Store response ID for next request
            if result.get("responseId"):
                self.storage.set(conversation_id, result["responseId"], model)
            return result
        except Exception as e:
            print(f"[StatefulClient] Stateful API unavailable, using stateless: {e}")

        # Final fallback to /v1/chat/completions
        history = full_history or messages
        return self._call_stateless_api(history, model, max_tokens, temperature, tools)

    def _call_stateful_api(
        self,
        messages: List[Dict],
        previous_response_id: Optional[str],
        model: str,
        max_tokens: int,
        temperature: float,
        tools: Optional[List[Dict]]
    ) -> Dict[str, Any]:
        """Call the /v1/responses stateful endpoint"""
        endpoint = f"{self.base_url}/v1/responses"

        payload = {
            "model": model,
            "messages": messages,
            "max_tokens": max_tokens,
            "temperature": temperature
        }

        if previous_response_id:
            payload["previous_response_id"] = previous_response_id

        if tools:
            payload["tools"] = tools

        print(f"[StatefulClient] POST {endpoint} (previous_response_id: {previous_response_id or 'none'})")

        response = requests.post(
            endpoint,
            json=payload,
            headers={
                "Content-Type": "application/json",
                "Authorization": "Bearer not-needed"
            },
            timeout=self.timeout
        )

        if response.status_code == 400:
            error_data = response.json()
            if "invalid_response_id" in str(error_data):
                raise ValueError("invalid_response_id")

        response.raise_for_status()
        data = response.json()

        content = ""
        tool_calls = None
        if data.get("choices"):
            choice = data["choices"][0]
            content = _strip_thinking(choice.get("message", {}).get("content", ""))
            tool_calls = choice.get("message", {}).get("tool_calls")

        return {
            "response": content,
            "toolCalls": tool_calls,
            "responseId": data.get("id"),
            "usedStateful": True,
            "usage": data.get("usage", {}),
            "raw": data
        }

    def _call_stateless_api(
        self,
        messages: List[Dict],
        model: str,
        max_tokens: int,
        temperature: float,
        tools: Optional[List[Dict]]
    ) -> Dict[str, Any]:
        """Fallback to /v1/chat/completions stateless endpoint"""
        endpoint = f"{self.base_url}/v1/chat/completions"

        payload = {
            "model": model,
            "messages": messages,
            "max_tokens": max_tokens,
            "temperature": temperature,
            "stream": False
        }

        if tools:
            payload["tools"] = [
                {
                    "type": "function",
                    "function": {
                        "name": t.get("function", {}).get("name"),
                        "description": t.get("function", {}).get("description"),
                        "parameters": t.get("function", {}).get("parameters")
                    }
                }
                for t in tools
            ]

        print(f"[StatefulClient] Fallback to stateless: POST {endpoint}")

        response = requests.post(
            endpoint,
            json=payload,
            headers={
                "Content-Type": "application/json",
                "Authorization": "Bearer not-needed"
            },
            timeout=self.timeout
        )
        response.raise_for_status()
        data = response.json()

        content = ""
        tool_calls = None
        if data.get("choices"):
            choice = data["choices"][0]
            content = _strip_thinking(choice.get("message", {}).get("content", ""))
            tool_calls = choice.get("message", {}).get("tool_calls")

        return {
            "response": content,
            "toolCalls": tool_calls,
            "responseId": None,
            "usedStateful": False,
            "usage": data.get("usage", {}),
            "raw": data
        }

    def reset_conversation(self, conversation_id: str) -> None:
        """Reset a conversation's state (clear response ID)"""
        self.storage.delete(conversation_id)
        print(f"[StatefulClient] Reset conversation: {conversation_id}")

    def clear_all_conversations(self) -> None:
        """Clear all conversation states (called on model switch)"""
        self.storage.clear()
        print("[StatefulClient] Cleared all conversations")

    def get_stats(self) -> Dict[str, Any]:
        """Get storage statistics"""
        return self.storage.get_stats()


# Singleton instance
_client_instance: Optional[StatefulLMStudioClient] = None


def get_stateful_client(**kwargs) -> StatefulLMStudioClient:
    """Get the singleton StatefulLMStudioClient instance"""
    global _client_instance
    if _client_instance is None:
        _client_instance = StatefulLMStudioClient(**kwargs)
    return _client_instance


def reset_stateful_client() -> None:
    """Reset the singleton (for testing)"""
    global _client_instance
    _client_instance = None
