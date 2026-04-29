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
        "prompt": """You are an intent router for a RAG-based financial document assistant covering Apple, Google/Alphabet, and Microsoft.

Route queries to:
- "tools": questions about specific company financials, revenue, earnings, market share, product launches, AI strategies, executive statements, or any factual data that requires document lookup from annual reports, 10-K filings, or news articles.
- "general": greetings, general knowledge questions not requiring document data, meta-questions about the system, how-to questions, or conversational queries.

When in doubt, route to "tools" to ensure factual accuracy from source documents.""",
        "labels": ["production"],
        "config": {
            "model": "anthropic.claude-haiku-4-5",
            "temperature": 0.0,
            "max_tokens": 256,
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

    def warmup(self):
        for name, spec in DEFAULT_PROMPTS.items():
            labels = spec.get("labels", ["production"])
            for label in labels:
                self.ensure_prompt(name=name, label=label)


prompt_service = PromptService()

if settings.ENABLE_LANGFUSE:
    with contextlib.suppress(Exception):
        prompt_service.warmup()
