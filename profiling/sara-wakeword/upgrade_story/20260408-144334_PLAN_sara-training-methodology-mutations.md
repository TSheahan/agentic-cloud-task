# Plan: sara-training-methodology-mutations

**Session date:** Wednesday 8 April 2026

---

## Methodology mutation table

Accumulated across two research/review cycles with search-specialist agent,
curated by project agent, approved by operator. This table drove the Target
State composition and profile integration.

| # | Parameter / Item | Previous | Refined | Rationale |
|---|-----------------|----------|---------|-----------|
| 1 | `n_samples` | 3,000 | 10,000 | OWW community practice; highest-leverage change for service-ready quality |
| 2 | `n_samples_val` | 500 | 2,000 | Matching scale |
| 3 | Adversarial phrase set | 6 phrases | ~20 curated | Phonetic-similarity expansion; exclude wake-phrase-containing utterances (deployment context: no one named Sara present) |
| 4 | Adversarial sample count | Matches positives | Matches positives (10k/2k) | Consistent coverage |
| 5 | Voice diversity | Primarily "Allie" | ≥5 Cartesia voices, varied prosody | Speaker diversity dominates generalisation in OWW's frozen-embedding pipeline |
| 6 | RIR sourcing | Optional/manual | Mandatory, HF automated | `davidscripka/MIT_environmental_impulse_responses` makes this zero-friction |
| 7 | `augmentation_rounds` | 1 | 2 | Standard for production-quality OWW training |
| 8 | `steps` | 25,000 | 50,000 | Linear scaling with data volume |
| 9 | `batch_n_per_class` adv/pos | 50 / 50 | 70 / 70 | Prevents under-sampling expanded dataset |
| 10 | Custom verifier | Not used | Standard post-training step | Lightweight logistic regression on ~3 real clips; near-zero cost, high FP reduction for single-user deployment |
| 11 | Threshold tuning | Ad hoc on-device | FAR/FRR protocol, result as deployment metadata | Threshold is a deployment parameter, not training config |
| 12 | Iteration cap | One-shot | 2 iterations max | Prevents open-ended refinement; re-evaluate methodology if 2 iterations don't converge |
| 13 | `background_clips/` | 60s silence placeholder | Representative ambient recommended | Silence = no effective noise augmentation; distinct from ACAV100M (feature-level) |
| 14 | `target_false_positives_per_hour` | 0.5 | 0.5 (confirmed) | Validated against OWW community norms (0.2–0.5); appropriate for home/kitchen |

## Unchanged parameters

`model_type: dnn`, `layer_size: 32`, `max_negative_weight: 1500`,
`batch_n_per_class` ACAV: 1024, Piper deprecation status.

## Deferred items

- **Tier 2 real voice corpus** (200–500 recorded clips for training mix) — separate work item requiring recording protocol, not a gate for this round
- **Voice cloning** via Cartesia — requires recorded material not yet available
- **Supplemental background audio** beyond minimal ambient — nice-to-have, not gating

## Files modified

1. `profiling/sara-wakeword/oww-training-env.profile.md` — Target State, Apply, Audit
2. `profiling/sara-wakeword/hey_sara_model.yml` — all parameter changes
3. `profiling/sara-wakeword/adversarial_phrases.example.txt` — expanded to 20 phrases
