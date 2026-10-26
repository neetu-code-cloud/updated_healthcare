"""Clinician oversight console for the UC004 assistant.

Run with:
    streamlit run reviewer_app.py

A licensed clinician reviews every held item and records approve / approve with edits /
reject, with a note. Until then the answer is never released to the requester.
"""
from __future__ import annotations

import getpass

import streamlit as st

import review_queue

st.set_page_config(page_title="Clinician Oversight Console", page_icon="🩺", layout="wide")

CONFIDENCE_COLOUR = {"High": "green", "Moderate": "orange", "Low": "red"}

st.title("Clinician Oversight Console")
st.caption(
    "Contoso Health System - CHS-POL-001 section 6. Training environment with fictional "
    "policies. Not for real patient care."
)

with st.sidebar:
    st.subheader("Reviewer")
    reviewer = st.text_input("Your name or UPN", value=getpass.getuser())
    st.divider()
    st.subheader("Queue")
    try:
        for status, count in review_queue.counts().items():
            st.metric(status.replace("_", " ").title(), count)
    except Exception as exc:  # noqa: BLE001 - surface auth/config problems in the UI
        st.error(f"Cannot read the queue: {exc}")
    if st.button("Refresh", use_container_width=True):
        st.rerun()

view = st.radio("Show", ["Pending", "Decided"], horizontal=True, label_visibility="collapsed")

if view == "Pending":
    items = review_queue.list_items(review_queue.PENDING)
    if not items:
        st.success("No items awaiting review.")
    for item in items:
        urgency = item.get("urgency", "routine")
        header = f"{'🔴 URGENT' if urgency == 'urgent' else '🕒 Routine'} · {item['question'][:90]}"
        with st.expander(header, expanded=len(items) == 1):
            left, right = st.columns([3, 2])
            with left:
                st.markdown("**Question**")
                st.write(item["question"])
                st.markdown("**Draft answer from the assistant**")
                edited = st.text_area(
                    "Draft answer", value=item["draft_answer"], height=220,
                    key=f"draft-{item['RowKey']}", label_visibility="collapsed",
                )
            with right:
                confidence = item.get("confidence", "Low")
                st.markdown(
                    f"**Confidence** :{CONFIDENCE_COLOUR.get(confidence, 'grey')}[{confidence}]"
                )
                st.markdown("**Why it was routed**")
                st.info(item.get("review_reason") or "not recorded")
                st.markdown("**Citations**")
                citations = item.get("citations") or []
                if citations:
                    for citation in citations:
                        detail = f" — {citation['detail']}" if citation.get("detail") else ""
                        st.markdown(f"- {citation['document']}{detail}")
                else:
                    st.warning("No citations. Treat as ungrounded.")
                st.markdown("**Requested by**")
                st.write(item.get("requester", "unknown"))
                st.caption(f"Queued {item.get('created_at', '')} · id {item['RowKey']}")

            note = st.text_input("Reviewer note", key=f"note-{item['RowKey']}")
            approve, approve_edit, reject = st.columns(3)

            def record(decision: str, final: str | None) -> None:
                if not reviewer.strip():
                    st.error("Enter your name in the sidebar before recording a decision.")
                    return
                review_queue.decide(
                    item["RowKey"], decision=decision, reviewer=reviewer.strip(),
                    note=note, final_answer=final,
                )
                st.success(f"Recorded: {decision.replace('_', ' ')}")
                st.rerun()

            with approve:
                if st.button("Approve", key=f"a-{item['RowKey']}", use_container_width=True):
                    record(review_queue.APPROVED, item["draft_answer"])
            with approve_edit:
                if st.button("Approve with edits", key=f"e-{item['RowKey']}", use_container_width=True):
                    record(review_queue.APPROVED_WITH_EDITS, edited)
            with reject:
                if st.button("Reject", key=f"r-{item['RowKey']}", type="primary", use_container_width=True):
                    record(review_queue.REJECTED, "")

else:
    rows = []
    for status in review_queue.DECISIONS:
        for item in review_queue.list_items(status):
            rows.append({
                "id": item["RowKey"],
                "decision": status.replace("_", " "),
                "question": item["question"][:80],
                "reviewer": item.get("reviewer", ""),
                "decided": item.get("decided_at", ""),
                "note": item.get("reviewer_note", ""),
            })
    if rows:
        st.dataframe(rows, use_container_width=True, hide_index=True)
    else:
        st.info("Nothing has been reviewed yet.")
