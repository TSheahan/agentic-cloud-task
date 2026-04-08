# Project Agent Review — Grok Response 2

## Overall

This response closes the five open questions with concrete, primary-source
grounded answers. We're now at the point where the methodology mutations are
specified tightly enough to draft the updated Target State. One item needs
curation before acceptance.

---

## Per-item review

### 1. Adversarial phrase list — ACCEPT with curation

The list has 26 entries but contains three categories that need separating:

**Category A — Genuinely confusable (keep as adversarial negatives):**
Phonetically close phrases a listener or detector might mistake for "hey
sara": hey sarah, hey serra, say sara, say sarah, hey tara, hey zara, hey
sorry, say ra, hey sarrah.

**Category B — Orthographic variants TTS may pronounce identically (remove
or test):** "hey saraa", "hey sarra", "hey saraah" — Cartesia may render
these indistinguishable from "hey sara" or "hey sarah". If the audio is
identical to the positive phrase, training on them as negatives is
counterproductive (teaches the model to reject its own wake word). These
should be tested with Cartesia before inclusion; drop any that sound like
the target.

**Category C — Wake-word-in-context phrases (separate concern):**
"hey there sara", "hey sara please", "sara come here", "hey sara now",
"hey sara hi", "hey sara bye", "hey sara yeah", "hey sarah come", "hey
sarah sorry", "hey sara there", "sara hey", "hey saraa please". These
contain the actual wake phrase embedded in longer utterances. Training the
model to reject these means it would suppress activation when Tim says
"hey Sara, come here" — which is almost certainly a genuine wake intent.

**Decision:** Category C should be excluded from adversarial negatives
entirely. The wake word detector should fire on any utterance that begins
with "hey sara" regardless of what follows. These phrases would actively
degrade the model.

**Additionally missing (genuinely confusable, should be added):**
- "hey Clara" / "hey Kara" / "hey Lara" / "hey Mara" (rhyming names)
- "hey sora" (vowel shift)
- "a sara" (weak leading syllable)

**Curated list for methodology (approximately 20 entries):**
```
hey sarah
hey serra
hey sarrah
say sara
say sarah
hey tara
hey zara
hey sorry
say ra
hey there
hey Clara
hey Kara
hey Lara
hey Mara
hey sora
a sara
hey sorry ah
hey siri
hey Ciara
hey Farrah
```

This covers: consonant swaps (s→t, s→z, s→k, s→l, s→m, s→f), vowel
shifts (a→o, a→e), rhyming names, leading syllable weakness, and the
existing set. ~20 distinct phonetic targets is sufficient for a 2-word
wake phrase.

### 2. Steps and batch_n_per_class scaling — ACCEPT

- `steps: 50000` (from 25000) — linear scaling with data volume, well-
  justified.
- `batch_n_per_class` adversarial/positive: 70 (from 50) — prevents
  under-sampling the expanded dataset.
- `max_negative_weight: 1500` unchanged — agreed, class-weighting not
  data-volume dependent.
- ACAV batch stays at 1024.

Clean, one-line YAML edits. No wall-time concern on g4dn.xlarge.

### 3. Custom verifier — ACCEPT (confirmed as methodology item)

The API is concrete and exactly as hoped:
- `train_custom_verifier()` — one function call
- Inputs: 3 WAV clips of Tim + ~10s of non-wakeword speech
- Output: `.pkl` file loaded alongside the base ONNX model
- Inference: `custom_verifier_models` parameter on `Model()`

**Important dependency note:** The verifier requires a small number of
Tim's real recordings (3 positive clips + brief speech). This is NOT the
same scope as Tier 2 (200–500 clips with recording protocol). Three clips
can be recorded on a phone in 30 seconds. This dependency is trivially
satisfiable and should not be treated as a deferral.

**Methodology decision:** The verifier is a standard post-training step.
The 3 required clips are a deployment-time input, not a training-time
input — they're recorded after the base model is trained, using the
deployment hardware.

### 4. FP target — CONFIRMED, no change

`target_false_positives_per_hour: 0.5` is appropriate for home/kitchen
deployment. OWW bundled models use 0.2; community custom runs span 0.2–0.5.
Our value sits at the permissive end of the normal range, which is correct
for a single-user home where occasional FPs are low-cost.

### 5. background_clips vs ACAV100M — CONFIRMED, clarification absorbed

Pipeline stages are now clear:
- `background_clips/` = raw WAVs for noise overlay during **augmentation**
  (before feature extraction). Creates realistic far-field conditions.
- ACAV100M = pre-extracted **features** for the **DNN training** negative
  class.

**Implication for the silence placeholder:** A 60s silence WAV means the
augmentation step adds no realistic noise — clips are augmented with
silence, which is effectively no noise augmentation at all. With RIRs now
mandatory (adding reverb), the noise dimension is the remaining weak point.

**Methodology decision:** Upgrade `background_clips/` from "placeholder
accepted" to "should contain representative ambient audio." This doesn't
need to be elaborate — even a few minutes of kitchen ambient recorded on a
phone would be a material improvement over silence. But it's not a hard
gate: the model will still train and the ACAV100M negatives provide the
heavy lifting during DNN training. Mark as "recommended upgrade."

---

## Citation note

Grok's claim that `oww_train_shim` "already passes voice params" for
multi-voice Cartesia generation is an implementation claim I should verify
against the actual `generate_samples.py` script before we rely on it. The
methodology (≥5–10 voices) is accepted regardless; the tooling may need a
small update.

---

## Final mutation table (complete)

| # | Parameter / Item | Current | Refined |
|---|-----------------|---------|---------|
| 1 | `n_samples` | 3,000 | 10,000 |
| 2 | `n_samples_val` | 500 | 2,000 |
| 3 | Adversarial phrase set | 6 phrases | ~20 (curated phonetic list) |
| 4 | Adversarial sample count | Matches positives | Matches positives (10k/2k) |
| 5 | Voice diversity | Primarily "Allie" | ≥5 Cartesia voices, varied prosody |
| 6 | RIR sourcing | Optional/manual | Mandatory, HF automated |
| 7 | `augmentation_rounds` | 1 | 2 |
| 8 | `steps` | 25,000 | 50,000 |
| 9 | `batch_n_per_class` adv/pos | 50 / 50 | 70 / 70 |
| 10 | Custom verifier | Not used | Standard post-training step |
| 11 | Threshold tuning | Ad hoc on-device | FAR/FRR protocol, result as deployment metadata |
| 12 | Iteration cap | One-shot | 2 iterations max |
| 13 | `background_clips/` | 60s silence | Representative ambient recommended |
| 14 | `target_false_positives_per_hour` | 0.5 | 0.5 (confirmed appropriate) |

**Unchanged:** `model_type: dnn`, `layer_size: 32`, `max_negative_weight: 1500`,
`batch_n_per_class` ACAV: 1024, Piper deprecation.

**Deferred:** Tier 2 real voice corpus (200–500 clips), voice cloning.

---

## Readiness assessment

We have enough material to draft the updated Target State methodology. The
research loop with Grok can close after this turn unless the adversarial
phrase curation or background_clips upgrade raises new questions.

Recommended next step: compose the refined methodology as an updated
Target State section, incorporating the 14-row mutation table above.
