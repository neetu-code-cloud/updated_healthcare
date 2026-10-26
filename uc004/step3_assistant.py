#!/usr/bin/env python3
"""LAB PART 3 - human oversight.

An answer reaches the requester only when it is safe to release. Everything else is held in
a review queue until a licensed clinician approves, edits or rejects it (CHS-POL-001 s6).

Run:
    python step3_assistant.py "What does the sepsis pathway require in the first hour?"
    python step3_assistant.py --urgent "..."
    python step3_assistant.py --status <review-id>

Then open the clinician console in a second terminal:
    streamlit run reviewer_app.py
"""
from __future__ import annotations

import argparse
import getpass

import review_queue
from ask_agent import ask


def should_hold(result: dict) -> tuple[bool, str]:
    """Decide whether this answer must be held for clinician review.

    Per CHS-POL-001, hold the answer when any of these is true:
      * the agent set requires_clinician_review
      * confidence is "Low"
      * there are no citations (an uncited answer is ungrounded by definition)

    Fail closed: if you are unsure, hold it.
    """

    # Fail closed if the agent response itself is invalid.
    if not isinstance(result, dict):
        return True, "Invalid agent response; clinician review required."

    # Hold whenever the agent explicitly requests clinician review.
    if result.get("requires_clinician_review") is True:
        return (
            True,
            result.get("review_reason") or "Agent requested clinician review.",
        )

    # Low-confidence answers must always be reviewed.
    confidence = result.get("confidence")

    if confidence == "Low":
        return True, "Low-confidence answer requires clinician review."

    # Fail closed if confidence is missing or invalid.
    if confidence not in {"High", "Moderate"}:
        return True, "Missing or invalid confidence; clinician review required."

    # An answer without citations is ungrounded and must be held.
    citations = result.get("citations")

    if not isinstance(citations, list) or not citations:
        return True, "Answer has no citations and cannot be released."

    # Fail closed if any citation is malformed or lacks a document.
    for citation in citations:
        if not isinstance(citation, dict) or not citation.get("document"):
            return True, "Answer contains an invalid citation; clinician review required."

    # All release conditions have been satisfied.
    return False, ""


def handle(question: str, *, requester: str, urgent: bool = False) -> dict:
    result = ask(question)
    hold, reason = should_hold(result)

    if not hold:
        return {"released": True, "result": result}

    queued = dict(result)
    queued["review_reason"] = result.get("review_reason") or reason

    item_id = review_queue.enqueue(
        question=question,
        result=queued,
        requester=requester,
        urgency="urgent" if urgent else "routine",
    )

    return {
        "released": False,
        "review_id": item_id,
        "reason": queued["review_reason"],
        "result": result,
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)

    parser.add_argument(
        "question",
        nargs="?",
    )

    parser.add_argument(
        "--urgent",
        action="store_true",
        help="CHS-POL-002 Tier 2 timing",
    )

    parser.add_argument(
        "--requester",
        default=None,
    )

    parser.add_argument(
        "--status",
        metavar="REVIEW_ID",
    )

    args = parser.parse_args()

    if args.status:
        item = review_queue.get_item(args.status)

        if item is None:
            print(f"No review item {args.status}")
            return

        print(f"status   : {item['status']}")
        print(f"question : {item['question']}")

        if item["status"] == review_queue.PENDING:
            print(
                f"queued   : {item['created_at']} "
                f"({item['urgency']})"
            )

            print(
                "\nHeld for clinician review. "
                "Nothing is released until a clinician decides."
            )

        else:
            print(
                f"reviewer : {item['reviewer']} "
                f"at {item['decided_at']}"
            )

            print(
                f"note     : {item['reviewer_note']}"
            )

            print(
                f"\n{item['final_answer']}"
            )

        return

    if not args.question:
        parser.error(
            "a question is required unless --status is used"
        )

    outcome = handle(
        args.question,
        requester=args.requester or getpass.getuser(),
        urgent=args.urgent,
    )

    result = outcome["result"]

    print(f"\nQ: {args.question}\n")

    if outcome["released"]:
        print(result["answer"])

        print(
            f"\nConfidence: {result['confidence']}"
        )

        for citation in result["citations"]:
            detail = (
                f" - {citation['detail']}"
                if citation.get("detail")
                else ""
            )

            print(
                f"  * {citation['document']}{detail}"
            )

    else:
        print(
            "Held for clinician review - "
            "not released to the requester."
        )

        print(
            f"\nReason    : {outcome['reason']}"
        )

        print(
            f"Review ID : {outcome['review_id']}"
        )

        print(
            f"Timing    : "
            f"{'within 15 minutes (Tier 2)' if args.urgent else 'within 1 business hour'}"
        )

        print(
            f"\nCheck later with: "
            f"python step3_assistant.py --status {outcome['review_id']}"
        )


if __name__ == "__main__":
    main()
 