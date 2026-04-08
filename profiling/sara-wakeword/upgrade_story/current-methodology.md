# Current Wake Word Training Methodology

Extracted from `profiling/sara-wakeword/oww-training-env.profile.md`,
`domain-knowledge.md`, and `hey_sara_model.yml`. This document captures
**methodology** — the decisions, rationale, and constraints that shape
training — not implementation mechanics (instance provisioning, SSH,
pip commands, directory layout).

---

## 1. Pipeline architecture (inherited from OWW)

OWW does not train end-to-end on raw audio. The pipeline is:

```
TTS WAVs → augmentation (noise / reverb / gain)
         → mel spectrogram
         → frozen Google speech embedding model → feature vectors (.npy)
         → small DNN classifier (trainable)
         → ONNX export
```

The trainable DNN is tiny (2 hidden layers × 32 units). Training is fast
once features are extracted. The expensive part is generating and augmenting
synthetic speech samples.

**Implication:** model quality is dominated by *data quality and diversity*,
not by model architecture or hyperparameter tuning. Methodology refinement
should focus on the sample generation tier.

## 2. Sample generation strategy

### 2.1 Positive samples

- **Source:** Cartesia cloud TTS (preferred single provider on the happy path).
  Voice: "Allie" (25-year-old female) plus additional voices for diversity.
- **Phrase:** "hey sara" (the `target_phrase`).
- **Variation dimensions:** voice identity, speed, pitch, emphasis,
  leading/trailing silence — varied across the generated set.
- **Count:** ≥ 3,000 train / ≥ 500 test (from `n_samples` / `n_samples_val`
  in `hey_sara_model.yml`).

### 2.2 Adversarial negatives

- **Purpose:** teach the model to reject phonetically close phrases.
- **Current phrase set:**
  - "hey siri", "hey sarah", "hey zara", "hey sorry", "say ra", "hey there"
- **Count:** ≥ 3,000 train / ≥ 500 test (matching positive counts).
- **Source:** same Cartesia TTS pipeline, driven by `--phrases-file`.
- **Open question (from domain-knowledge.md):** this list should be expanded
  based on false-positive analysis after first model validation.

### 2.3 Tier 2 — real voice (planned, not yet executed)

- Record ~200–500 samples of "hey Sara" from Tim in natural conditions
  (kitchen, varied distance/volume/mood).
- Role: validation gold; may also be mixed into training for personalisation.
- **Status in current profile:** mentioned in domain-knowledge.md as a tier
  but not yet integrated into the training profile or pipeline.

### 2.4 Background negatives (pre-computed)

- `openwakeword_features_ACAV100M_2000_hrs_16bit.npy` — 2,000 hours of
  negative speech features from the ACAV100M dataset (HuggingFace).
- `validation_set_features.npy` — false-positive validation features
  (HuggingFace).
- `background_clips/` — at least one audio file for false-positive training.
  Current profile accepts a minimal 60s silence WAV as a first-pass
  placeholder.

### 2.5 Room impulse responses (RIRs)

- MIT RIR dataset for reverb augmentation.
- **Status:** optional for first pass; training degrades gracefully (skips
  reverb augmentation).
- **Open:** not yet automated for download; current profile marks `mit_rirs/`
  as "skip on first pass if not automated."

## 3. Training configuration decisions

From `hey_sara_model.yml`:

| Parameter | Value | Rationale |
|-----------|-------|-----------|
| `model_type` | `dnn` | OWW default; small footprint for edge deployment |
| `layer_size` | 32 | OWW default; 2 layers × 32 units |
| `steps` | 25,000 | — |
| `augmentation_rounds` | 1 | Single pass augmentation |
| `max_negative_weight` | 1,500 | Controls negative class weighting during training |
| `target_false_positives_per_hour` | 0.5 | Acceptable FP rate for the deployment scenario |
| `batch_n_per_class` | ACAV=1024, adversarial=50, positive=50 | Heavy bias toward background negatives per batch |

### 3.1 Augmentation

- Noise overlay from `background_clips/`.
- Reverb from `mit_rirs/` (when available).
- Gain variation (implied by OWW `--augment_clips`).
- Single augmentation round.

### 3.2 Training invocation

- `--augment_clips --train_model` without `--generate_clips`.
- Clips are pre-placed; OWW's Piper TTS path is bypassed via an import
  shim (`oww_train_shim/`) that satisfies the `generate_samples` import
  without being callable.

## 4. Model validation

### 4.1 Smoke test (automated)

`smoke_test_model.py` — runs on the deployment target (Pi):
- Load ONNX model via OWW `Model` class.
- Feed silent frames → confirm zero scores (no false activation on silence).
- Optional live mic test: 15 seconds of listening, threshold 0.3, report
  detections.

### 4.2 Threshold tuning (open)

- Default threshold in smoke test: 0.3.
- Previous model (hey_jarvis) used 0.5.
- Domain knowledge flags that "Sara will need its own threshold found
  empirically on the Pi with real ambient conditions."
- No systematic threshold-tuning methodology is expressed yet.

### 4.3 False-positive validation during training

- `target_false_positives_per_hour: 0.5` in the training config.
- Validated against `validation_set_features.npy` (pre-computed).

## 5. Integration target

Target consumer: `recorder_child.py` in the `raspberry-ai` project
(`forked_assistant` voice agent).

- Load model with `OWWModel(wakeword_model_paths=[path])`.
- Match on `wakeword == "hey_sara"` with configurable threshold.
- Both model path and wake word key should be configurable (not hardcoded).

## 6. Compute platform (methodology-relevant subset)

- **GPU required for:** augmentation throughput and feature extraction (ONNX
  embedding). DNN training itself is fast.
- **Instance class:** g4dn.xlarge (T4, 16 GB VRAM) — sufficient for OWW.
- **Estimated wall time:** 2–4 hours total (generation + augmentation +
  training). DNN training alone is minutes.
- **Cost envelope:** $2–5 per full run on spot.

## 7. Piper deprecation

Piper TTS (OWW's upstream default generator) is deprecated in this project.
Rationale: lower quality than Cartesia for producing realistic training data.
Retained only as Appendix A in the profile for fallback documentation.

---

## Methodology gaps and open questions

1. **Adversarial phrase coverage** — current set is 6 phrases; no systematic
   phonetic-similarity analysis has been done to ensure coverage.
2. **Tier 2 (real voice) data** — planned but not integrated.
3. **RIR sourcing** — MIT RIRs are referenced but not reliably downloaded;
   first pass proceeds without reverb augmentation.
4. **Background audio quality** — a 60s silence WAV is accepted as minimal
   placeholder. Real-world background audio is not part of the current
   pipeline.
5. **Threshold tuning** — no systematic methodology; empirical on-device
   testing is the stated approach.
6. **Sample count calibration** — 3,000/500 train/test per polarity is the
   current target. Domain knowledge mentions 10,000–50,000 as a target
   range for positive clips. The gap between config and aspiration is not
   explained.
7. **Voice diversity** — Cartesia "Allie" is the primary voice. The degree
   of voice diversity across the generated set is not specified.
8. **Augmentation depth** — single augmentation round. No rationale for not
   doing more.
9. **Verifier model** — OWW supports a secondary verifier for FP reduction.
   Domain knowledge notes "may be overkill for single-user home deployment"
   but leaves it open.
10. **Model iteration loop** — no methodology for iterating on a model
    (generate → train → validate → adjust → retrain). The profile is
    structured as a one-shot run.
