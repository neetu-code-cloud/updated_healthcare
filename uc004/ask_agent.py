"""Calls your agent and parses the response contract. Nothing to edit here.

`ask()` returns the contract fields plus:
    _context   - what the knowledge base actually returned (used by the evaluation in Part 4)
    _telemetry - response id, tool-call count, token usage
"""
from __future__ import annotations

import json
import re
from typing import Any

from azure.ai.projects import AIProjectClient
from azure.identity import AzureCliCredential
from openai import BadRequestError

import lab_config as cfg


# Models occasionally emit retrieval markers such as "【6:1†source】" or "[ref_id:2]" despite
# instructions not to. Strip them so downstream consumers never see them.
_MARKER = re.compile(r"\s*(?:【[^】]*】|\[ref_id:\s*\d+\])")


def _clean(text: str) -> str:
    return _MARKER.sub("", text).strip()


def _sanitize(payload: dict[str, Any]) -> dict[str, Any]:
    if isinstance(payload.get("answer"), str):
        payload["answer"] = _clean(payload["answer"])
    if isinstance(payload.get("review_reason"), str):
        payload["review_reason"] = _clean(payload["review_reason"])
    for citation in payload.get("citations") or []:
        for key in ("document", "detail"):
            if isinstance(citation.get(key), str):
                citation[key] = _clean(citation[key])
    return payload

_FAIL_CLOSED = {
    "confidence": "Low",
    "citations": [],
    "requires_clinician_review": True,
    "review_reason": "The agent did not return a valid response contract.",
}


def ask(question: str, agent_name: str | None = None) -> dict[str, Any]:
    project = AIProjectClient(endpoint=cfg.PROJECT_ENDPOINT, credential=AzureCliCredential())
    client = project.get_openai_client(agent_name=agent_name or cfg.AGENT_NAME)

    try:
        response = client.responses.create(input=question)
    except BadRequestError as exc:
        # The platform content filter can block a prompt before the agent ever sees it -
        # jailbreak detection fires on instruction-override attempts, for example. That is a
        # refusal, not a crash: report it and fail closed.
        if "content_filter" not in str(exc):
            raise
        return {
            "answer": "The platform content filter blocked this request before it reached the agent.",
            "confidence": "Low",
            "citations": [],
            "requires_clinician_review": True,
            "review_reason": "Blocked by the Azure OpenAI content filter.",
            "_context": [],
            "_telemetry": {"response_id": None, "contract_parsed": False,
                           "knowledge_base_calls": 0, "input_tokens": None,
                           "output_tokens": None, "blocked_by_content_filter": True},
        }

    text = response.output_text or ""
    try:
        payload = json.loads(text)
        parsed = True
    except json.JSONDecodeError:
        payload = {"answer": text, **_FAIL_CLOSED}
        parsed = False

    tool_calls = [item for item in (response.output or []) if getattr(item, "type", "") == "mcp_call"]
    context: list[str] = []
    for call in tool_calls:
        raw = getattr(call, "output", None)
        if not raw:
            continue
        try:
            context.extend(
                d.get("content", "") for d in json.loads(raw).get("documents", []) if d.get("content")
            )
        except (json.JSONDecodeError, AttributeError):
            context.append(str(raw))

    payload = _sanitize(payload)
    payload["_context"] = context
    payload["_telemetry"] = {
        "response_id": response.id,
        "contract_parsed": parsed,
        "knowledge_base_calls": len(tool_calls),
        "input_tokens": getattr(response.usage, "input_tokens", None),
        "output_tokens": getattr(response.usage, "output_tokens", None),
    }
    return payload
