# agent-eval-gate

**A proposed release-decision gate for LLM agents that accounts for uncertainty and differential bias in judge measurements.**

> **Status: M1 in progress.** The measurement protocol (M0) is drafted and the interface contract is revised to it. The harness, statistical gate, and demo are future work.

## Project goal

Investigate whether bias-aware comparisons of baseline and candidate agents reduce false release decisions on verifiable-outcome benchmarks. Report missed improvements, statistical power, abstention, and evaluation cost alongside any benefit.

This is a hypothesis to test, not an established performance claim. The intended output is a release decision with its evidence and limitations.

Read [Project Goals and Direction](PROJECT_DIRECTION.md) for the current measurement questions, proposed stages, and claims and limits.

## Proposed approach

1. Define the outcome and use a pinned executable subset of BFCL. Use direct verification when it is affordable.
2. Run both agents on the same tasks with isolated state and randomized judge presentation order.
3. Investigate judge discrepancies on equal-outcome cases and test whether calibration applies beyond that selected subset. Equal correctness does not imply equal clarity or helpfulness.
4. Compare raw thresholds, naive confidence intervals, and calibrated methods against independently held-out verification outcomes.
5. Begin with one comparison and a fixed sample size. Account for sampling and calibration uncertainty and explain unresolved decisions.

The first planned agent variant is **retrieval-augmented generation (RAG)** using embeddings and vector retrieval of tool documentation. The gate evaluates whether retrieval improves verified outcomes. **MCP** tool transport, SWE-bench, small-judge distillation, and advanced statistical methods remain later extensions.

## Boundaries

Truth-tied cases do not automatically identify differential bias on all tasks. A correction from one domain or judge version does not automatically transfer to another. The gate cannot establish the authenticity of supplied records or the validity of an incomplete or compromised verifier. It is not a general safety assessment or a validation of subjective quality scores.

## Repository

- [PROJECT_DIRECTION.md](PROJECT_DIRECTION.md): current goals and design discussion.
- [PROTOCOL.md](PROTOCOL.md): measurement protocol for the BFCL pilot (draft v0.1).
- [MILESTONES.md](MILESTONES.md) and [milestones/](milestones/): roadmap and guided milestone docs.
- [src/agent_eval_gate/contract.py](src/agent_eval_gate/contract.py): interface contract, revised to protocol §9.
- [tests/test_contract.py](tests/test_contract.py): contract tests (`uv run --extra dev pytest`).
- [AGENTS.md](AGENTS.md): working instructions for coding agents.

No usable gate or evaluation CLI is available yet.

## License

MIT — see [LICENSE](LICENSE).
