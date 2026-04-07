# Session Summary — 2026-04-06

## What happened

Decided on **Sara** as the wake word name for the voice assistant. Leading sibilant,
two syllables, natural female name, matches the ~25yo Cartesia "Allie" voice.

Built the full training pipeline in `~/sara/hudsons-bay/`:

- **`orchestrate.py`** — Pi-side script that launches an AWS g4dn.xlarge spot instance,
  uploads training config, runs OWW training remotely, pulls back `hey_sara.onnx`,
  and tears down all AWS resources. One command: `python orchestrate.py`

- **`aws_train.sh`** — runs on the AWS instance. Installs OWW, downloads training data,
  generates synthetic "hey Sara" clips via Piper TTS, augments, trains, exports ONNX.

- **`hey_sara_model.yml`** — OWW training config. Hudson's Bay settings: 3000 samples,
  25k steps, relaxed FP target (0.5/hr). Disposable first pass.

- **`smoke_test_model.py`** — validates the .onnx on the Pi (silent frame check + live mic).

- **`generate_samples.py`** — optional, generates Cartesia/ElevenLabs WAV samples.
  Not needed for this pass.

Also added `synthesise_to_file()` and `--out` flag to
`mvp-modules/forked_assistant/src/tts.py` (all three cloud backends).

## What blocked

Three AWS permission issues, resolved in sequence:
1. `ec2:CreateTags` — added to policy ✓
2. `iam:CreateServiceLinkedRole` for spot.amazonaws.com — added to policy ✓
3. `MaxSpotInstanceCountExceeded` — new account has 0 vCPU quota for G-family spot.
   Quota increase request filed: **case 177543724400520**

## Pickup instructions

### When the quota increase is approved:

```bash
source ~/venv/bin/activate
python ~/sara/hudsons-bay/orchestrate.py
```

That's it. The script handles everything and tears down after itself.
Expect 2-4 hours wall time, ~$1-2 in spot cost.

If it succeeds, `model/hey_sara.onnx` will appear in this directory.
Then:

```bash
python ~/sara/hudsons-bay/smoke_test_model.py model/hey_sara.onnx --live
```

### If something goes wrong:

```bash
# See what's running
python ~/sara/hudsons-bay/orchestrate.py --dry-run

# Clean up any leftover AWS resources
python ~/sara/hudsons-bay/orchestrate.py --teardown-only
```

### If the orchestrator fails for a new reason:

The error will be in the terminal output. Common things to check:
- AWS credentials: `AWS_ACCESS_KEY_ID_TRAINING` / `AWS_SECRET_ACCESS_KEY_TRAINING` in `~/.env`
- Region: `AWS_DEFAULT_REGION=ap-southeast-2` in `~/.env`
- AMI: `ami-084f512b0521b5fb4` (Deep Learning Base OSS Nvidia, Ubuntu 22.04, ap-southeast-2)
- The `aws_train.sh` script expects Python 3.10 or 3.11 on the instance (the DL AMI has both)

### After hey_sara.onnx works on Pi:

Integration target is `mvp-modules/forked_assistant/src/recorder_child.py`:
- Line 449: `OWWModel()` → `OWWModel(wakeword_model_paths=[...])`
- Line 509: `wakeword == "hey_jarvis"` → match the key from the new model
- Threshold (0.5) may need tuning for the new model

That integration is a separate change, not part of this Hudson's Bay pass.

## File inventory

```
~/sara/
  PLAN.md                              — full project plan (name rationale, training architecture, etc.)
  hudsons-bay/
    SESSION_SUMMARY.md                 ← this file
    README.md                          — quick reference
    orchestrate.py                     — THE COMMAND
    aws_train.sh                       — runs on AWS instance
    hey_sara_model.yml                 — OWW training config
    smoke_test_model.py                — Pi-side validation
    generate_samples.py                — TTS sample generator (optional)
    model/                             — hey_sara.onnx lands here
    samples/                           — TTS samples land here (optional)

~/raspberry-ai/mvp-modules/forked_assistant/src/tts.py
    — modified: added synthesise_to_file(), _synthesise_pcm(), _write_wav(), --out CLI flag
```
