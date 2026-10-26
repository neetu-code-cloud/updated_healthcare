# Extensions — going deeper on UC004

You have a working, grounded, evaluated assistant. These challenges take it from *working* to
*defensible*: the questions an evaluation panel asks when the demo has already gone well.

Each one is independent. Pick what interests you — nobody is expected to do all seven.

| # | Challenge | Difficulty | Rough time | What it proves |
|---|---|---|---|---|
| [E1](E1-extend-the-corpus.md) | Add your own policy and route between sources | Moderate | 45 min | The corpus is not fixed, and routing is a design decision |
| [E2](E2-tune-retrieval.md) | Measure retrieval effort instead of guessing | Moderate | 40 min | You can justify a configuration with numbers |
| [E3](E3-red-team.md) | Red-team your own agent | Hard | 60 min | It holds up against someone trying to break it |
| [E4](E4-verify-citations.md) | Prove the citations are real | Hard | 45 min | A cited answer is not the same as a grounded one |
| [E5](E5-cost-and-latency.md) | Put a price and a latency budget on it | Moderate | 45 min | It could survive a finance conversation |
| [E6](E6-confidence-calibration.md) | Check whether "High" means high | Hard | 45 min | Self-reported confidence is worth something |
| [E7](E7-conflicting-guidance.md) | Handle a policy that was updated | Hard | 50 min | It behaves sensibly when the corpus disagrees with itself |

## The rule that applies to all of them

**Finish with evidence, not an assertion.** Every challenge has an acceptance test. A panel
will believe a number and a repeatable command; it will not believe "it seemed to work".

**And do not break what already works.** After any change, run the base evaluation again:

```powershell
python step4_evaluate.py --local-only
```

19/19 must still pass. A change that fixes one thing and quietly breaks two is a regression,
and regressions are the most common way these systems degrade in production.

## Your sandbox

You have write access to one folder of your own in the shared storage account:

```
sandbox/<your-alias>/...
```

The approved `corpus` container stays read-only for everyone — that is deliberate, and it is
also why E1 uses the sandbox rather than adding to the corpus directly. Anything you upload
lives under your alias and cannot disturb anyone else's work.

## How these are assessed

They map onto the capstone's own criteria:

| Criterion | Challenges that speak to it |
|---|---|
| Solution design & architecture | E1, E7 |
| Technical implementation | E1, E4, E6 |
| Deployment readiness | E2, E3, E5 |
| Business value | E5 |
| Innovation | E4, E7 |
| Presentation & defence | all of them — bring the numbers |
