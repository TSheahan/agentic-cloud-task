# Sara Wake Word — Domain Knowledge

Durable reference for the "hey Sara" custom OpenWakeWord model. Distilled
from the original project plan and two Hudson's Bay training sessions
(2026-04-06; logs under [deprecated-hudsons-bay/](deprecated-hudsons-bay/AGENTS.md)).

---

## Name rationale

Sara. Two syllables, natural female name, leading sibilant (S) provides a
strong high-frequency spectral anchor for wake word detection. Matches the
~25-year-old female voice persona (Cartesia "Allie"). No false-positive
risk in the household.

---

## OWW training pipeline architecture

OWW models are not trained end-to-end on raw audio. The pipeline is:

```
TTS samples (wav) → augmentation (noise/reverb/gain) → mel spectrogram
→ Google speech embedding model (frozen) → feature vectors (.npy)
→ small DNN classifier (trainable) → export to ONNX
```

The DNN is tiny (default: 2 hidden layers x 32 units). Training is fast
once features are extracted. The expensive part is generating and
augmenting the synthetic speech samples.

### What the OWW pipeline expects

- **Positive samples:** thousands of audio clips of "hey Sara" in varied
  voices.
- **Adversarial negatives:** phonetically similar phrases.
- **Background negatives:** hours of speech/music/noise for false-positive
  training (pre-computed feature sets on HuggingFace).
- **Room impulse responses (RIRs):** for reverb augmentation (MIT RIR
  dataset).
- **False-positive validation data:** pre-computed features for FP-rate
  measurement.

---

## Two-tier sample generation strategy

The convergence profile’s **happy path** uses **Cartesia** for bulk WAVs; Piper is
**deprecated** (Appendix A only). Relative to upstream OWW (Piper-first), this
project prefers higher-quality cloud TTS for training data:

**Tier 1 — Synthetic (bulk, diverse)**
- **Cartesia API** (preferred happy path for this repo — Allie voice + other voices for diversity)
- ElevenLabs API, Deepgram (optional alternates via `generate_samples.py`)
- Piper TTS (OWW upstream default — **deprecated** for product-quality training here; parked in `oww-training-env.profile.md` Appendix A)
- Target: 10,000-50,000 positive clips across all sources
- Vary: voice, speed, pitch, emphasis, leading/trailing silence

**Tier 2 — Tim's voice (ground truth)**
- Record ~200-500 samples of "hey Sara" in natural conditions
- Kitchen setting, varied distance/volume/mood
- Validation gold; can be mixed into training for personalisation

`generate_samples.py` implements Tier 1 Cartesia/ElevenLabs generation
using the `forked_assistant` TTS backends.

---

## Adversarial negative phrases

Phonetically close to "hey Sara", used for negative training:

- "hey siri"
- "hey sarah"
- "hey zara"
- "hey sorry"
- "say ra"
- "hey there"

This list should be expanded based on false-positive analysis after the
first model is validated.

---

## Dependency landscape

The OWW training pipeline has known dependency friction (upstream GitHub
issue #317):

- Requires Python 3.10-3.11 (PyTorch 1.13.1 incompatible with 3.12+)
- `pip install -e ".[full]"` may pull NumPy 2.x; must pin `numpy<2` after
- Broken transitive deps: pyarrow, fsspec, webrtcvad
- MIT RIR dataset needs manual preprocessing
- HuggingFace rate limiting on training data download
- Upstream filename renames (e.g. `openwakeword_features.npy` renamed to
  `validation_set_features.npy`)

Mitigation options explored:
1. **Containerised trainer:** `github.com/briankelley/atlas-voice-training/`
2. **lgpearson1771/openwakeword-trainer:** automated 13-step pipeline with
   compat patches
3. **Manual env setup** on AWS with pinned deps (early approach; see archived
   [`deprecated-hudsons-bay/aws_train.sh`](deprecated-hudsons-bay/aws_train.sh))

---

## Compute matrix

| Stage | Where | Notes |
|---|---|---|
| TTS sample generation (Cartesia/ElevenLabs) | Pi or any machine with API keys | API calls, not compute-bound |
| TTS sample generation (Piper) | AWS instance | Piper runs locally, benefits from CPU |
| Audio augmentation | AWS instance | CPU-bound, parallelisable |
| Feature extraction | AWS instance | Uses ONNX embedding model |
| DNN training | AWS instance | GPU, fast (~minutes) |
| ONNX export | AWS instance | Trivial |
| Validation on real audio | Pi | Final integration test |

### Cost estimates

- Instance: `g4dn.xlarge` (T4 GPU, 16 GB VRAM) — ~$0.53/hr on-demand,
  ~$0.16/hr spot
- Or: `g5.xlarge` (A10G, 24 GB VRAM) — ~$1.01/hr on-demand
- Estimated training time: 1-2 hours with GPU (after data generation)
- Data generation (TTS synthesis + augmentation): additional 1-2 hours
- Total estimated cost: $2-5 for a full run on spot

---

## Integration target

File: `mvp-modules/forked_assistant/src/recorder_child.py` (in the
separate `raspberry-ai` project).

Current:
```python
self.model = OWWModel()
if (wakeword == "hey_jarvis" and score > 0.5 ...):
```

Target:
```python
self.model = OWWModel(wakeword_model_paths=[str(MODEL_PATH)])
if (wakeword == "hey_sara" and score > WAKE_THRESHOLD ...):
```

Both the model path and wake word key should be configurable (env var or
config), not hardcoded.

---

## Open questions

1. **Threshold tuning:** 0.5 was set for hey_jarvis. Sara will need its own
   threshold found empirically on the Pi with real ambient conditions.
2. **Piper vs Cartesia/ElevenLabs mix:** Piper gives free diversity but
   lower quality. Cartesia/ElevenLabs give realism but cost per sample.
3. **Custom verifier model?** OWW supports a secondary verifier for
   reducing FP. May be overkill for a single-user home deployment.
4. **Container vs manual setup on AWS?** The manual approach worked (with
   fixes). Containerisation worth revisiting if the dep situation worsens.
