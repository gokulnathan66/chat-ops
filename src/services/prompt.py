from __future__ import annotations

import contextlib
import os
from typing import Any

from langfuse import Langfuse

from src.setting.config import settings

DEFAULT_PROMPTS: dict[str, dict[str, Any]] = {
    "rag_assistant": {
        "type": "text",
        "prompt": """You are an expert financial analyst assistant with deep knowledge of big tech companies — Apple, Google/Alphabet, and Microsoft.

You have access to a semantic document search tool that retrieves relevant information from indexed annual reports (10-K filings), financial summaries, and news articles.

Guidelines:
- Always use the semantic_document_search tool to retrieve relevant documents before answering questions about financials, revenues, strategies, or company-specific data.
- Cite the specific figures and sources you reference (e.g., "According to Microsoft's FY2025 10-K...").
- Be precise with numbers, dates, and financial metrics.
- If the retrieved documents do not contain enough information to answer fully, say so clearly rather than speculating.
- Do not fabricate financial figures, revenue numbers, or forward-looking projections.
- Structure responses with clear headings when comparing multiple companies or covering multiple topics.""",
        "labels": ["production"],
        "config": {
            "model": "anthropic.claude-haiku-4-5",
            "temperature": 0.1,
            "max_tokens": 2048,
        },
    },
    "general_assistant": {
        "type": "text",
        "prompt": """You are a helpful AI assistant specializing in technology, business, and financial topics.

Guidelines:
- Answer clearly and concisely.
- For questions about specific financial figures, earnings reports, or company data, let the user know that document search is available for precise data retrieval.
- Do not fabricate statistics, revenue figures, stock prices, or company-specific facts.
- Keep responses professional and well-structured.
- If asked about indexed documents or the knowledge base, explain that you can search for specific financial documents about Apple, Google/Alphabet, and Microsoft.""",
        "labels": ["production"],
        "config": {
            "model": "anthropic.claude-haiku-4-5",
            "temperature": 0.3,
            "max_tokens": 1024,
        },
    },
    "intent_router": {
        "type": "text",
        "prompt": """You are an intent router for a financial AI assistant. Route each user message to exactly one of four destinations:

- "tools": The user wants specific financial data, document search, or factual lookup (e.g. revenue, earnings, stock prices, company filings about Apple, Google/Alphabet, or Microsoft).
- "general": Conversational questions, greetings, or opinions that do not require document retrieval or any sensitive action.
- "escalate": The query is ambiguous, unanswerable, out of scope, or confidence < 0.5. Hand off to a human agent.
- "approval_required": The user is requesting ANY action that involves exporting, sharing, sending, or disclosing data — regardless of how the request is phrased (imperative, question, or polite ask). Examples that MUST route here:
    • "Export my chat history" → approval_required
    • "Share this conversation with my manager" → approval_required
    • "Send this data externally" → approval_required
    • "Can you export my data?" → approval_required (treat as an action request, not a capability question)
    • "Save and send my conversation" → approval_required
  For this route you MUST include action_payload with action_type, action_description, and risk_level (low/medium/high).

IMPORTANT: If a message mentions exporting, sharing, sending, or disclosing any data or conversation, always choose "approval_required" — never "general".

Always return valid JSON matching the schema. action_payload is required only for approval_required.""",
        "labels": ["production"],
        "config": {
            "model": "anthropic.claude-haiku-4-5",
            "temperature": 0.0,
            "max_tokens": 512,
        },
    },
}


class PromptService:
    def __init__(
        self,
        public_key: str | None = None,
        secret_key: str | None = None,
        host: str | None = None,
    ):
        self.client = Langfuse(
            public_key=public_key or os.getenv("LANGFUSE_PUBLIC_KEY"),
            secret_key=secret_key or os.getenv("LANGFUSE_SECRET_KEY"),
            host=host or os.getenv("LANGFUSE_HOST", "https://cloud.langfuse.com"),
        )
        self._cache: dict[str, Any] = {}

    def _cache_key(self, name: str, label: str) -> str:
        return f"{name}:{label}"

    def ensure_prompt(self, name: str, label: str = "production"):
        cache_key = self._cache_key(name, label)
        if cache_key in self._cache:
            return self._cache[cache_key]

        try:
            prompt = self.client.get_prompt(name, label=label)
            self._cache[cache_key] = prompt
            return prompt
        except Exception:
            if name not in DEFAULT_PROMPTS:
                raise ValueError(
                    f"Prompt '{name}' not found in Langfuse and no local default is defined."
                ) from None

            spec = DEFAULT_PROMPTS[name]
            labels = spec.get("labels") or [label]

            self.client.create_prompt(
                name=name,
                type=spec.get("type", "text"),
                prompt=spec["prompt"],
                labels=labels,
                config=spec.get("config", {}),
            )

            prompt = self.client.get_prompt(name, label=label)
            self._cache[cache_key] = prompt
            return prompt

    def get_prompt(self, name: str, label: str = "production"):
        return self.ensure_prompt(name=name, label=label)

    def render(self, name: str, label: str = "production", **variables) -> str:
        prompt = self.ensure_prompt(name=name, label=label)
        return prompt.compile(**variables)

    def get_langchain_prompt(self, name: str, label: str = "production", **precompiled_variables) -> str:
        prompt = self.ensure_prompt(name=name, label=label)
        return prompt.get_langchain_prompt(**precompiled_variables)

    def upsert_prompt(self, name: str, label: str = "production") -> None:
        """Force-create a new Langfuse prompt version from DEFAULT_PROMPTS, then refresh cache."""
        if name not in DEFAULT_PROMPTS:
            raise ValueError(f"No default prompt defined for '{name}'")
        spec = DEFAULT_PROMPTS[name]
        labels = spec.get("labels") or [label]
        self.client.create_prompt(
            name=name,
            type=spec.get("type", "text"),
            prompt=spec["prompt"],
            labels=labels,
            config=spec.get("config", {}),
        )
        cache_key = self._cache_key(name, label)
        self._cache.pop(cache_key, None)

    def warmup(self):
        for name, spec in DEFAULT_PROMPTS.items():
            labels = spec.get("labels", ["production"])
            for label in labels:
                self.ensure_prompt(name=name, label=label)


prompt_service = PromptService()

if settings.ENABLE_LANGFUSE:
    with contextlib.suppress(Exception):
        prompt_service.warmup()
