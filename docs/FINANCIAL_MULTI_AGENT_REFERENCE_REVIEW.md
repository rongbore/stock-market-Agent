# Financial Multi-Agent Reference Review

Research date: 2026-11-07

This note records public upstream projects reviewed to guide the financial research
agent architecture. The repository does not vendor or copy their implementation
code in this change. Any future code reuse requires a file-level license and
dependency review.

## Shortlist

| Project | License observed | Relevant upstream design | Proposed use here |
|---|---|---|---|
| [TauricResearch/TradingAgents](https://github.com/TauricResearch/TradingAgents) | Apache-2.0 | Specialist analyst roles, separate bull/bear researchers, a research manager, risk management, structured outputs, point-in-time data safeguards, provider abstractions and resumable graph execution | Best domain reference. Improve role prompts, bull/bear challenge, structured research-plan schema, data provenance and checkpoint/resume. Do not import its trading/execution path. |
| [YairLutaty/multi-agent-debate](https://github.com/YairLutaty/multi-agent-debate) | No license file confirmed in inspected repository metadata/tree | Evidence-first shared research, bounded rebuttal rounds, deterministic stop policy, saved transcripts, reproducible evaluation and explicit limitations | Architecture inspiration only unless a compatible license is added. Reimplement the ideas independently: evidence ledger, novelty-based early stop, transcript schema and deterministic quality metrics. |
| [virattt/ai-hedge-fund](https://github.com/virattt/ai-hedge-fund) | MIT | Separate investor/analyst agents, risk and portfolio modules, backtesting/research modules, paper-ledger and reproducible session concepts | Use only as a design reference for separating research output from risk constraints and for audit-friendly run records. Do not connect brokerage or execute orders. |
| [langchain-ai/langgraph](https://github.com/langchain-ai/langgraph) | MIT | Stateful graph orchestration, explicit transitions, checkpointing and resumable workflows | Evaluate as an orchestration dependency only if the current lightweight Python orchestration becomes difficult to maintain. Avoid adding a large framework dependency prematurely. |

## Findings from upstream documentation and source inspection

### TradingAgents

The README describes an analyst team that works in parallel, followed by bull/bear researchers
that debate the analyst reports, then a trader and risk/portfolio management stages. The
repository also exposes structured schemas, a graph setup, checkpointer, point-in-time data
windows, and provider clients. Its own README states that it is a research framework and not
investment advice.

Applicable improvements:
- Keep the five domain specialists independent for the first pass.
- Add explicit bull and bear challenge perspectives after the specialist pass.
- Make the moderator a structured research manager, not a majority-vote counter.
- Require all claims to point to the same immutable evidence snapshot.
- Keep risk review independent and capable of blocking a conclusion.
- Record model/provider/data configuration and support safe resume after interruption.

### Evidence-grounded debate project

The inspected project documents:
- one shared research/evidence pool before debate;
- bounded rebuttal rounds;
- deterministic termination based on novelty and maximum rounds;
- a saved transcript and deterministic evaluation metrics;
- a clear warning that lexical metrics do not prove factual correctness.

Applicable improvements:
- Avoid re-fetching or silently changing source evidence between discussion turns.
- Stop early when successive rounds add little new information, while retaining a hard round cap.
- Save the complete transcript and per-agent positions.
- Evaluate source coverage, dissent preservation, and evidence linkage separately; do not claim these are truth scores.

License note: no license was confirmed in the inspected repository. Do not copy its source code unless licensing is clarified.

### AI Hedge Fund

The inspected README and license identify an educational/research project under MIT, with
separate agent, risk, portfolio and backtesting areas. It explicitly disclaims real trading
and investment advice.

Applicable improvements:
- Separate research conclusions from risk constraints.
- Persist run provenance and auditable decision records.
- Keep all portfolio/trading/execution functionality out of this PR.

## Proposed target architecture

1. Immutable evidence snapshot: source URL/provider, retrieval time, publication time,
   instrument, period, currency/unit, hash and point-in-time eligibility.
2. Five independent specialists: market data, fundamentals, technical indicators,
   quantitative validation and risk.
3. Adversarial review: bullish and bearish challenge roles inspect the same evidence and
   the five reports; each must cite specific claims and counter-evidence.
4. Bounded group discussion: at most two rounds by default, deterministic early stop when
   novelty is low, no model-controlled unbounded loops.
5. Moderator synthesis: structured verdict, evidence-backed rationale, unresolved disputes,
   missing data, confidence rationale and scenarios.
6. Deterministic policy layer: severe evidence-backed risk cannot be erased by a later
   model response; uncertainty and minority objections remain visible.
7. Audit artifact: immutable run ID, code SHA, model/provider, prompt/schema versions,
   source snapshot IDs, call counts, latency, token usage if available, transcript hash
   and final report.

## Non-goals and safety boundaries

- No broker credentials, brokerage connections, order routing or live execution.
- No automated investment action.
- No model-generated price target without independently validated data and explicit
  assumptions.
- No consensus-as-truth shortcut.
- No copied upstream code without license compatibility and attribution review.

## Sources

- https://github.com/TauricResearch/TradingAgents
- https://github.com/YairLutaty/multi-agent-debate
- https://github.com/virattt/ai-hedge-fund
- https://github.com/langchain-ai/langgraph
