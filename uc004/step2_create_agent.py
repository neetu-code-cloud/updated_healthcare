#!/usr/bin/env python3
"""LAB PART 2 - build the grounded agent.

Two things happen here:

  1. A project connection is created so the agent can call your knowledge base with the
     project's managed identity (no keys).
  2. An agent version is created with the knowledge base attached as an MCP tool, your
     instructions, and a strict JSON response contract.

Run:
    python step2_create_agent.py             # create connection + agent
    python step2_create_agent.py --ask "..." # ask your agent one question

Fill in the TODOs. Your agent must satisfy CHS-POL-001: ground every answer, cite it,
label confidence, and defer clinical decisions to a clinician.
"""
from __future__ import annotations

import argparse
import json

import requests
from azure.ai.projects import AIProjectClient
from azure.ai.projects.models import MCPTool, PromptAgentDefinition
from azure.identity import AzureCliCredential

import lab_config as cfg

# --------------------------------------------------------------------- instructions

# TODO 1: write the system instructions for your agent.
#
# The assistant must, per the Contoso policies in the corpus:
#   - call the knowledge base tool for every clinical/policy question, and answer ONLY
#     from what it returns (never from its own medical knowledge);
#   - say plainly when the corpus does not cover the question;
#   - cite the documents it used, and never invent a citation;
#   - label confidence High / Moderate / Low (CHS-POL-001 section 5);
#   - refuse and defer anything patient-specific: diagnosis, treatment changes, doses,
#     paediatric / pregnant / unstable patients, result interpretation, end-of-life
#     (CHS-POL-001 section 4), naming the escalation route from CHS-POL-002;
#   - never repeat back patient identifiers (CHS-POL-004 section 2);
#   - set requires_clinician_review whenever it defers, is Low confidence, or cannot cite.
#
# Tip: be explicit and testable. Part 4 will score these behaviours.
INSTRUCTIONS = """
You are the Contoso Health System Clinical Knowledge Grounding Assistant.

Follow these rules for every clinical or Contoso policy question:

1. GROUNDING
- Always call the approved_corpus knowledge base tool before answering.
- Answer only from information returned by the knowledge base.
- Never use your own medical knowledge, general knowledge, assumptions, or memory to fill gaps.
- If the retrieved corpus does not contain enough information to answer the question, state plainly that the approved corpus does not contain the answer.
- Never invent, infer, or guess facts that are absent from the retrieved corpus.

2. CITATIONS
- Cite only documents actually returned by the knowledge base.
- Never invent a document name, citation, reference, policy number, or source.
- Put sources only in the "citations" array.
- Do not include inline reference markers such as [ref_id:1] or source-reference markers in the "answer", "detail", "review_reason", or any other string field.
- Each citation must contain the actual source document name and a short description of the information supported by that source.
- If an answer cannot be supported by a real citation, set confidence to "Low" and requires_clinician_review to true.

3. CONFIDENCE
Return exactly one confidence value:
- "High": the retrieved approved corpus directly and clearly supports the answer.
- "Moderate": the retrieved approved corpus supports the answer but the information is incomplete, indirect, or requires combining multiple retrieved sources.
- "Low": the retrieved approved corpus does not adequately support the answer, the answer cannot be cited, or the corpus does not cover the question.

4. PATIENT-SPECIFIC REQUESTS
Defer any patient-specific request involving diagnosis, treatment decisions or changes, medication doses, result interpretation, paediatric patients, pregnant patients, unstable patients, or end-of-life decisions.

For such requests:
- Do not provide clinical advice.
- Do not provide a diagnosis, treatment recommendation, medication dose, threshold, interpretation, or other clinical guidance.
- Do not include retrieved clinical facts as helpful context.
- The answer must contain only a concise deferral and the escalation route supported by the approved corpus, including CHS-POL-002 where retrieved.
- Set requires_clinician_review to true.
- Give a review_reason explaining that the request requires clinician review.

5. PATIENT IDENTIFIERS / PHI
- Do not repeat, quote, echo, transform, summarize, or include patient identifiers supplied by the user.
- If patient identifiers or PHI are provided, do not reproduce them in any response field.

6. CLINICIAN REVIEW
Set requires_clinician_review to true whenever:
- the request is deferred;
- confidence is "Low"; or
- the response cannot be supported by an actual citation from the retrieved corpus.

Otherwise, requires_clinician_review may be false.

When requires_clinician_review is true, populate review_reason with a concise reason.
When clinician review is not required, return an empty string for review_reason.

7. OUT-OF-CORPUS QUESTIONS
If the approved corpus does not contain the requested information:
- explicitly state that the approved corpus does not contain the answer;
- do not answer from model knowledge;
- set confidence to "Low";
- set requires_clinician_review to true;
- explain the corpus gap in review_reason.

8. RESPONSE FORMAT
Return only an object satisfying the supplied JSON schema.
Do not add text before or after the JSON response.
The "answer" must never contain inline reference markers.
All source information belongs in "citations".
""".strip()

# --------------------------------------------------------------------- response contract (given)

RESPONSE_SCHEMA = {
    "type": "object",
    "additionalProperties": False,
    "required": [
        "answer",
        "confidence",
        "citations",
        "requires_clinician_review",
        "review_reason",
    ],
    "properties": {
        "answer": {"type": "string"},
        "confidence": {
            "type": "string",
            "enum": ["High", "Moderate", "Low"],
        },
        "citations": {
            "type": "array",
            "items": {
                "type": "object",
                "additionalProperties": False,
                "required": ["document", "detail"],
                "properties": {
                    "document": {"type": "string"},
                    "detail": {"type": "string"},
                },
            },
        },
        "requires_clinician_review": {"type": "boolean"},
        "review_reason": {"type": "string"},
    },
}


def create_connection() -> None:
    """Let the agent authenticate to the knowledge base as the project's managed identity."""
    access_token = AzureCliCredential().get_token(
        "https://management.azure.com/.default"
    ).token

    headers = {
        "Authorization": f"Bearer {access_token}"
    }

    url = (
        f"https://management.azure.com{cfg.PROJECT_RESOURCE_ID}/connections/"
        f"{cfg.CONNECTION_NAME}?api-version=2025-10-01-preview"
    )

    # GOTCHA: 'audience' is only applied when a connection is CREATED. Updating an existing
    # connection keeps the old value and the agent fails at run time with
    # "Failed to fetch access token ... Missing required query parameter 'audience'".
    requests.delete(
        url,
        headers=headers,
        timeout=60,
    )

    response = requests.put(
        url,
        headers=headers,
        timeout=60,
        json={
            "name": cfg.CONNECTION_NAME,
            "type": "Microsoft.MachineLearningServices/workspaces/connections",
            "properties": {
                "authType": "ProjectManagedIdentity",
                "category": "RemoteTool",
                "target": cfg.KB_MCP_URL,
                "isSharedToAll": True,
                "audience": "https://search.azure.com/",
                "metadata": {
                    "ApiType": "Azure"
                },
            },
        },
    )

    response.raise_for_status()

    print(f"connection ready: {cfg.CONNECTION_NAME}")


def create_agent() -> None:
    if "TODO" in INSTRUCTIONS:
        raise SystemExit(
            "Write your instructions in INSTRUCTIONS (TODO 1) before creating the agent."
        )

    # TODO 2: attach your knowledge base as an MCP tool.
    #   server_label          - a short name for the tool
    #   server_url            - cfg.KB_MCP_URL
    #   project_connection_id - cfg.CONNECTION_NAME (this is what authenticates the call)
    #   allowed_tools         - the knowledge base exposes exactly one: "knowledge_base_retrieve"
    #   require_approval      - "never" for this lab (the oversight step is human review of answers)
    knowledge_tool = MCPTool(
        server_label="approved_corpus",
        server_url=cfg.KB_MCP_URL,
        project_connection_id=cfg.CONNECTION_NAME,
        allowed_tools=["knowledge_base_retrieve"],
        require_approval="never",
    )

    project = AIProjectClient(
        endpoint=cfg.PROJECT_ENDPOINT,
        credential=AzureCliCredential(),
    )

    agent = project.agents.create_version(
        agent_name=cfg.AGENT_NAME,
        definition=PromptAgentDefinition(
            model=cfg.CHAT_DEPLOYMENT,
            instructions=INSTRUCTIONS,
            tools=[knowledge_tool],

            # TODO 3: the agent must not answer clinical questions without retrieving first.
            # "required" forces tool use; "auto" could allow the model to skip retrieval.
            tool_choice="required",

            text={
                "format": {
                    "type": "json_schema",
                    "name": "clinical_answer",
                    "strict": True,
                    "schema": RESPONSE_SCHEMA,
                }
            },
        ),
    )

    print(
        f"agent ready: {agent.name} "
        f"(version {getattr(agent, 'version', '?')})"
    )


def ask(question: str) -> None:
    from ask_agent import ask as run  # noqa: PLC0415 - keeps the import local to this path

    result = run(question)

    print(
        json.dumps(
            {
                k: v
                for k, v in result.items()
                if not k.startswith("_")
            },
            indent=2,
        )
    )


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)

    parser.add_argument(
        "--ask",
        metavar="QUESTION",
        help="ask your agent a question",
    )

    args = parser.parse_args()

    if args.ask:
        ask(args.ask)
        return

    create_connection()
    create_agent()

    print(
        "\nTry it:  python step2_create_agent.py --ask "
        "\"What does the sepsis pathway require in the first hour?\""
    )


if __name__ == "__main__":
    main()