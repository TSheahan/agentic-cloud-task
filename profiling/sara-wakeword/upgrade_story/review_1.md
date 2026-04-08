# Project Agent Review — Grok Response 1

## Overall assessment

The response is well-structured, maps cleanly to the 10 gaps, and confirms
the Cartesia-first strategy is sound. Several items are directly actionable.
A few need calibration against this project's scope constraint: "reasonable
amount of refinement effort towards service-ready" — not research-grade
optimisation.

---

## Per-item review

### 1. Adversarial phrase coverage — ACCEPT with clarification needed

The recommendation to expand the phrase set systematically via phonetic
similarity is the right call. The proposed scale (≥10k train / ≥2k val) is
reasonable.

**Clarification needed:** The distinction between *adversarial negatives*
(phonetically close TTS clips, augmented to features) and *background
negatives* (ACAV100M, already at 2,000 hrs of pre-computed features) needs
to stay sharp. The "100k+ adversarial" claim — is that for custom wake
words at OWW's scale, or for OWW's own bundled models? For a custom keyword
with a finite confusable set, the phrase-expansion strategy matters more
than raw count. How many distinct phrases is realistic for "hey sara"?

**Ask Grok:** Can you give a concrete expanded phrase list (20–30 entries)
for "hey sara" using the phonetic-similarity approach you described? That
would let us assess whether 10k samples across that set is right or whether
we'd need to weight per-phrase.

### 2. Tier 2 real voice — DEFER (scope boundary)

The methodology is sound (10–20% mix into training, remainder as validation
gold). However, "mandatory step before final training runs" overreaches the
scope. Recording 200–500 real utterances requires Tim, a Pi, dedicated time,
and a recording protocol — it's a separate work item, not part of this
training round's methodology refinement.

**Project decision:** Tier 2 is acknowledged as high-value and remains in
the methodology document as a *planned enhancement*, not a gate for the next
run. If Tim happens to have real recordings available, they should be mixed
in; otherwise the next run proceeds on pure synthetic.

### 3. RIR sourcing — ACCEPT (high value, low cost)

The finding that `davidscripka/MIT_environmental_impulse_responses` exists
on HuggingFace and is streamable is the single most actionable item in the
response. This closes the gap completely — reverb augmentation goes from
"optional, skip on first pass" to "standard, automated."

**Accepted into methodology:** RIRs are mandatory; sourced from HuggingFace
dataset. Reverb augmentation is no longer optional.

### 4. Background audio — ACCEPT (minor adjustment)

Retain ACAV100M as core background negatives. The recommendation to
supplement with real-world background clips is fine as an aspiration but
doesn't change the methodology for this round. The actual gap was the
`background_clips/` directory used during augmentation — a 60s silence WAV
is indeed a placeholder.

**Clarification needed:** Is the `background_clips/` directory (used for
augmentation-phase noise overlay) materially impactful when ACAV100M already
provides 2,000 hrs of negative features? Or is this directory primarily
about SNR mixing during the augmentation step before feature extraction?
The two are at different points in the pipeline and serve different purposes.

### 5. Threshold tuning — ACCEPT methodology, REJECT detail

The FAR/FRR curve approach with standardised on-device test suite is the
right methodology. However:

- "Document the chosen threshold in the model YAML" is **wrong** — the YAML
  is a training config. The threshold is a deployment parameter belonging to
  the integration target's config (e.g. env var or config file in
  `raspberry-ai`).
- The methodology should specify: *after training, a threshold-determination
  protocol runs on the deployment target, producing a recommended threshold
  that ships with the model as deployment metadata.*

### 6. Sample count — ACCEPT

≥10,000 train / ≥2,000 val positives is well-supported and directly
actionable. This is the primary YAML change (`n_samples: 10000`,
`n_samples_val: 2000`). Agreed this is high-leverage.

**Missing from Grok's analysis:** With 3× more data, do the training
hyperparameters need adjustment?
- `steps: 25000` — should this increase with more training features?
- `batch_n_per_class` ratios (ACAV=1024, adversarial=50, positive=50) —
  should the adversarial/positive batch fractions change?
- `max_negative_weight: 1500` — still appropriate?

**Ask Grok:** What does OWW documentation/community say about scaling
`steps` and `batch_n_per_class` when sample volume increases from 3k to 10k?

### 7. Voice diversity — ACCEPT

≥5–10 Cartesia voices with prosody variation is a clear, actionable target.

**Reject:** Voice cloning of Tim is out of scope for this round (same
reasoning as Tier 2 deferral — requires recorded material that may not
exist yet).

**Project note:** The `generate_samples.py` script's voice selection
mechanism needs to be checked — does it currently support multi-voice
generation, or only a single voice ID per invocation? This is implementation
but it determines whether the methodology is achievable with current tooling.

### 8. Augmentation depth — ACCEPT

`augmentation_rounds: 2` is a simple config change with plausible benefit.
No objection.

### 9. Verifier model — ACCEPT (strongest new finding)

This is the most interesting item. If OWW's custom verifier is truly a
lightweight logistic regression trained on ~3 positive clips + ~10s of
negative audio from Tim, it's:

- Essentially free to add.
- Dramatically reduces FP in single-user deployment.
- Does NOT require the full Tier 2 recording corpus — just a few clips.

This changes the verifier from "may be overkill" to "trivially cheap and
high-value." It should be a standard post-training step.

**Ask Grok:** Can you confirm the exact OWW API/workflow for custom verifier
models? Specifically: what inputs does it need, how is it trained, and how
is it loaded at inference time alongside the base model? Reference to
`custom_verifier_models.md` in OWW docs would be ideal.

### 10. Iteration loop — ACCEPT with scope calibration

The 2–3 iteration cycle is sound methodology. For this project's scope
constraint, cap at **2 iterations**:

1. Synthetic-only run with refined data (this round).
2. Deploy → collect FP/FN logs on Pi → add to adversarial set → retrain
   (next round, if warranted by FP rate).

The threshold-tuning protocol from item 5 naturally feeds into this.

---

## Gaps in the Grok response

Items the search specialist didn't address:

1. **Training hyperparameter scaling** — `steps`, `batch_n_per_class`,
   `max_negative_weight` as data volume increases. See item 6 above.
2. **`target_false_positives_per_hour: 0.5`** — is this the right target
   for a kitchen deployment? What do OWW community models typically target?
3. **The generate_samples.py voice parameter space** — methodology says
   "5–10 voices" but we need to know what Cartesia offers for this.
4. **Citation quality** — references to "arXiv:2201.00167" and "OWW issues
   #110/#255/#130" are not elaborated. Would like to know what specifically
   these say rather than taking them on trust.

---

## Accepted methodology mutations (so far)

| # | Change | From | To |
|---|--------|------|----|
| 1 | Positive sample count | 3,000 / 500 | 10,000 / 2,000 |
| 2 | Adversarial phrase set | 6 phrases | ~20–30 (pending expanded list) |
| 3 | Adversarial sample count | 3,000 / 500 | 10,000 / 2,000 (matching positives) |
| 4 | Voice diversity | Primarily "Allie" | ≥5–10 Cartesia voices |
| 5 | RIR sourcing | Optional/manual | Mandatory, HuggingFace automated |
| 6 | Augmentation rounds | 1 | 2 |
| 7 | Verifier model | Not used | Standard post-training step |
| 8 | Iteration loop | One-shot | 2-iteration cap |
| 9 | Threshold tuning | Ad hoc | FAR/FRR protocol on deployment target |

**Deferred:**
- Tier 2 real voice (planned enhancement, not gating)
- Voice cloning (requires real recordings)
- Background audio supplementation (ACAV100M sufficient for now)

---

## Questions for Grok (next turn)

1. Concrete expanded adversarial phrase list for "hey sara" (20–30 entries).
2. OWW guidance on scaling `steps` and `batch_n_per_class` with 10k samples.
3. Exact OWW custom verifier API/workflow (inputs, training, inference).
4. What does `target_false_positives_per_hour` typically look like in OWW
   community models? Is 0.5 appropriate for home/kitchen deployment?
5. The role of `background_clips/` vs ACAV100M in the pipeline — are these
   at different stages and serving different purposes?
