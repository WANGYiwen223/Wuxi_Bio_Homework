# Evaluation

Conversation evaluations. Keep test oracles outside model context.

Implemented: `scoring.py` checks persisted resolution/verification, resource completion, evidence, mutations and contextual handoff. `scripts/run_evaluation.py` runs isolated live conversations with simulated feedback/review. Structural scores do not establish diagnostic-text quality.
