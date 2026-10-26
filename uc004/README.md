# UC004 · Clinical Knowledge Grounding Agent — Lab

Microsoft FDE Use-Case Pack · Wipro AI Academy
**L200 → L300 · 4 hours · Microsoft Foundry + Foundry IQ**

Build a clinical knowledge assistant that answers only from an approved corpus of clinical
guidelines and hospital policy, cites what it used, labels its own confidence, hands every
patient-specific question to a clinician, and is then measured for groundedness.

> **Training environment.** "Contoso Health System" and every CHS document are fictional,
> written for this lab. The VA/DoD Clinical Practice Guidelines in the corpus are real,
> public-domain US federal publications. **Nothing here may be used for real patient care.**

## Start here

1. Open **[docs/lab-guide.md](docs/lab-guide.md)** and follow it from Part 0.
2. You will need the **lab environment handout** from your trainer — it has the endpoints,
   resource names and subscription id that go into your `.env` file. This repository ships
   placeholders only.

Quick setup on your lab VM (PowerShell as Administrator):

```powershell
Set-ExecutionPolicy -Scope Process Bypass -Force
.\setup-windows.ps1
```

Then copy `.env.example` to `.env`, paste in the handout values, set `LAB_ALIAS` to your lab
username, and continue with Part 1 of the guide.

## What you will build

```
  approved corpus (blob storage)
        │  extraction + embeddings
        ▼
  knowledge source ──► knowledge base (Foundry IQ)
                         │  query planning, reranking, cited answer synthesis
                         │  MCP, authenticated with a managed identity - no keys
                         ▼
                      your Foundry agent
                         │
            ┌────────────┴─────────────┐
            ▼                          ▼
   released to the requester    clinician review queue ──► review console
   (grounded, cited)            (deferred, low confidence, or uncited)
```

## What is in this repository

| Path | What it is |
|---|---|
| `docs/lab-guide.md` | The lab, in six parts, with checkpoints and troubleshooting |
| `step1_create_knowledge.py` | Part 1 — create your knowledge source and knowledge base (has TODOs) |
| `step2_create_agent.py` | Part 2 — create the connection and your grounded agent (has TODOs) |
| `step3_assistant.py` | Part 3 — human oversight routing (has a TODO) |
| `step4_evaluate.py` | Part 4 — behaviour checks and groundedness evaluation |
| `reviewer_app.py` | The clinician review console (Streamlit) |
| `lab_config.py`, `lab_search.py`, `ask_agent.py`, `review_queue.py` | Helper modules — nothing to edit |
| `questions.jsonl` | The 19 evaluation questions |
| `reference/policies/` | The fictional Contoso policies. **Read CHS-POL-001 first — it is the specification your agent must satisfy.** |
| `setup-windows.ps1` | One-time VM setup |
| `solutions/` | Reference solutions — try it yourself first, then compare |
| `extensions/` | Seven deeper challenges for when the core lab is done |

## Finished the lab?

The core lab gets you a working, grounded, evaluated assistant. **[extensions/](extensions/README.md)**
takes it from *working* to *defensible* — seven independent challenges covering retrieval tuning,
red-teaming, citation verification, cost and latency, confidence calibration and conflicting
policy versions. Each has an acceptance test, so you finish with evidence rather than an assertion.

Nobody is expected to do all seven. Pick the ones you would want to be asked about.

## Requirements

- A Windows lab VM with Python 3.12, the Azure CLI and VS Code (the lab image has these).
- An account that is a member of the lab participant group, so you can create agents and
  knowledge bases in the shared backend.

## Commands

```powershell
python lab_config.py                      # show the names your alias generates
python step1_create_knowledge.py          # create + ingest + test your knowledge base
python step1_create_knowledge.py --test   # re-run the test query
python step1_create_knowledge.py --delete # delete your knowledge objects
python step2_create_agent.py              # create your connection and agent
python step2_create_agent.py --ask "..."  # ask your agent
python step3_assistant.py "..."           # ask, with oversight routing
python step3_assistant.py --status <id>   # check a held item
streamlit run reviewer_app.py             # clinician review console
python step4_evaluate.py                  # evaluate your agent
```

## Licence and attribution

The VA/DoD Clinical Practice Guidelines referenced by this lab are works of the US federal
government and are in the public domain. The Contoso Health System documents in
`reference/policies/` are fictional training content written for this lab.
