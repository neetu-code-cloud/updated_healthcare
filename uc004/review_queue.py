"""Clinician oversight queue for the UC004 assistant, backed by Azure Table Storage.

Implements CHS-POL-001 section 6: every deferral and every low-confidence answer becomes a
review item that a licensed clinician must approve, edit or reject before the answer is
released. Nothing here lets the agent mark its own work as reviewed.
"""
from __future__ import annotations

import datetime as dt
import json
import os
import uuid
from typing import Any, Iterable

from azure.core.exceptions import ResourceExistsError
from azure.data.tables import TableClient, UpdateMode
from azure.identity import AzureCliCredential

import lab_config as cfg

STORAGE_ACCOUNT = cfg.STORAGE_ACCOUNT
TABLE_NAME = cfg.REVIEW_TABLE
TABLE_ENDPOINT = f"https://{STORAGE_ACCOUNT}.table.core.windows.net"

PENDING = "pending"
APPROVED = "approved"
APPROVED_WITH_EDITS = "approved_with_edits"
REJECTED = "rejected"
DECISIONS = (APPROVED, APPROVED_WITH_EDITS, REJECTED)


def _client() -> TableClient:
    client = TableClient(
        endpoint=TABLE_ENDPOINT,
        table_name=TABLE_NAME,
        credential=AzureCliCredential(),
    )
    try:
        client.create_table()
    except ResourceExistsError:
        pass
    return client


def _now() -> str:
    return dt.datetime.now(dt.timezone.utc).isoformat(timespec="seconds")


def enqueue(*, question: str, result: dict[str, Any], requester: str, urgency: str = "routine") -> str:
    """Create a review item and return its id. `result` is the agent's response contract."""
    item_id = uuid.uuid4().hex[:12]
    entity = {
        "PartitionKey": PENDING,
        "RowKey": item_id,
        "question": question,
        "draft_answer": result.get("answer", ""),
        "confidence": result.get("confidence", "Low"),
        "citations": json.dumps(result.get("citations", [])),
        "review_reason": result.get("review_reason", ""),
        "requester": requester,
        "urgency": urgency,                       # routine -> 1 business hour, urgent -> CHS-POL-002 Tier 2
        "agent_response_id": (result.get("_telemetry") or {}).get("response_id", ""),
        "created_at": _now(),
        "status": PENDING,
        "reviewer": "",
        "reviewer_note": "",
        "final_answer": "",
        "decided_at": "",
    }
    with _client() as table:
        table.create_entity(entity)
    return item_id


def list_items(status: str = PENDING) -> list[dict[str, Any]]:
    with _client() as table:
        items = list(table.query_entities(f"PartitionKey eq '{status}'"))
    for item in items:
        item["citations"] = json.loads(item.get("citations") or "[]")
    return sorted(items, key=lambda i: i.get("created_at", ""))


def get_item(item_id: str, status: str = PENDING) -> dict[str, Any] | None:
    with _client() as table:
        for item in table.query_entities(f"RowKey eq '{item_id}'"):
            item["citations"] = json.loads(item.get("citations") or "[]")
            return item
    return None


def decide(item_id: str, *, decision: str, reviewer: str, note: str = "", final_answer: str | None = None) -> None:
    """Record a clinician decision. The item moves out of the pending partition."""
    if decision not in DECISIONS:
        raise ValueError(f"decision must be one of {DECISIONS}")
    with _client() as table:
        entities: Iterable[dict[str, Any]] = table.query_entities(f"RowKey eq '{item_id}'")
        entity = next(iter(entities), None)
        if entity is None:
            raise KeyError(f"review item {item_id} not found")
        old_partition = entity["PartitionKey"]
        entity.update({
            "PartitionKey": decision,
            "status": decision,
            "reviewer": reviewer,
            "reviewer_note": note,
            "final_answer": final_answer if final_answer is not None else entity.get("draft_answer", ""),
            "decided_at": _now(),
        })
        table.create_entity(entity)                      # new partition
        table.delete_entity(old_partition, item_id)      # remove from the old one


def counts() -> dict[str, int]:
    result = {}
    for status in (PENDING, *DECISIONS):
        with _client() as table:
            result[status] = sum(1 for _ in table.query_entities(f"PartitionKey eq '{status}'", select=["RowKey"]))
    return result
