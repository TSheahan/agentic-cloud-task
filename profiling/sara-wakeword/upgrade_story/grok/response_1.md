**Search Specialist Report: Best Practices & Refinement Recommendations for "Hey Sara" Wake Word Training Methodology**

I've grounded this in current OWW documentation (creator-led practices), community discussions, training notebooks/examples, academic papers on adversarial augmentation, and related wake-word research. The core OWW pipeline (TTS → augmentation → Google embedding → small DNN) is already aligned with proven approaches—100% synthetic data routinely achieves strong real-world performance when data volume, diversity, and adversarial coverage are sufficient. Cartesia TTS (with its quality, voice variety, and parameter controls) is an excellent fit and superior to the deprecated Piper path; no need to pivot away from it.

Below I map directly to the **current methodology gaps** you listed, with targeted, actionable mutations. These keep the focus on *methodology* (decisions/rationale) rather than raw implementation details.

### 1. Adversarial Phrase Coverage (Gap #1)
**Current state**: Only 6 hand-picked phrases; no systematic phonetic analysis.  
**Best practice (from OWW repo, issues #110/#255/#130, and papers like arXiv:2201.00167)**: Expand aggressively using phonetically similar/confusable phrases generated via TTS. OWW explicitly supports `--custom_negative_phrases` or `--phrases-file` for this. Models with insufficient adversarial data show high false positives; scaling adversarial samples to ~100k+ (or at least 10× positives) is common in production-grade training. Papers recommend concatenated audio, partial masking, or TTS-synthesized confusing words.

**Proposed refinement**:
- Systematically expand the phrase set using phonetic similarity (e.g., ARPABET/CMUdict tools or simple Levenshtein on phonemes) to include variants like "hey sarah", "hey sara h", "say sara", "hey tara", "hey sarah", "hey serra", etc.
- Generate adversarial clips with the *same* Cartesia pipeline (Allie + additional voices, varied prosody).
- Target: ≥10k train / ≥2k val adversarial samples (matching or exceeding positive scale).
- Rationale: This directly reduces the dominant failure mode without changing architecture.

### 2. Tier 2 Real Voice Data (Gap #2)
**Current state**: Planned but not integrated.  
**Best practice (OWW creator + community notebooks)**: Even 100–500 real clips from the target speaker (Tim) dramatically improves FRR and personalization when mixed into the positive set (or used as validation gold). 100% synthetic works, but hybrid training consistently outperforms pure synthetic on real deployment audio.

**Proposed refinement**:
- Record 200–500 natural "hey Sara" utterances from Tim (kitchen, varied distance/volume/mood/background).
- Mix 10–20% of these real clips into the positive training set; keep the remainder as a separate validation tier.
- This becomes a mandatory step before final training runs.

### 3. RIR Sourcing & Automation (Gap #3)
**Current state**: Optional/manual MIT RIRs; first-pass skips reverb.  
**Best practice**: OWW evaluation and augmentation explicitly recommend RIRs for far-field realism (5–10 dB SNR noise + reverb). The OWW creator maintains a ready-to-use Hugging Face dataset: `davidscripka/MIT_environmental_impulse_responses` (271 × 16 kHz WAVs, ~8 MB, originally from MIT IR Survey).

**Proposed refinement**:
- Automate via `datasets.load_dataset("davidscripka/MIT_environmental_impulse_responses")` (streamable, no manual download).
- Make reverb augmentation mandatory (do not skip on first pass).
- Apply in 2+ augmentation rounds with varied room types.

### 4. Background Audio Quality (Gap #4)
**Current state**: ACAV100M + minimal silence placeholder.  
**Best practice**: OWW pre-trained models use ~30k hours of diverse negatives (ACAV100M speech/noise/music + Common Voice). Realistic SNR mixing (5–10 dB) + music/noise is standard.

**Proposed refinement**:
- Retain ACAV100M as core but supplement with additional real-world background clips (kitchen, TV, etc.) if available.
- Increase background duplication rate and ensure varied SNR in augmentation.

### 5. Threshold Tuning (Gap #5)
**Current state**: Empirical on-device only (default 0.3).  
**Best practice (OWW docs + Picovoice-style guides)**: Build a systematic loop using real ambient recordings + FAR/FRR curves. Default threshold is often 0.5; tune per deployment (home kitchen noise). Track target_false_positives_per_hour explicitly.

**Proposed refinement**:
- After each training run, run a standardized on-Pi test suite: 15–30 min continuous ambient audio + controlled "hey Sara" utterances.
- Plot FAR vs. threshold; target ≤0.5 FP/hour while keeping FRR <5%.
- Document the chosen threshold in the model YAML.

### 6. Sample Count Calibration (Gap #6)
**Current state**: 3k/500 per class.  
**Best practice**: "Several thousand" minimum; performance scales with volume (community examples: 10k–200k+ positives, 100k+ adversarial). OWW automatic training examples set `n_samples: 10000`, `n_samples_val: 2000`.

**Proposed refinement**:
- Bump to **≥10,000 train / ≥2,000 val positives** (Cartesia-generated).
- Match with adversarial count.
- This is the single highest-leverage change for "service-ready" quality.

### 7. Voice Diversity (Gap #7)
**Current state**: Primarily "Allie".  
**Best practice (OWW creator)**: Massive speaker diversity via multi-speaker TTS + latent-space mixing is the secret to generalization. Cartesia supports multiple voices + fine controls (pitch/speed/emotion).

**Proposed refinement**:
- Use ≥5–10 Cartesia voices (not just Allie).
- Explicitly vary speed (±20%), pitch (±10–20%), emphasis, leading/trailing silence, and emotion/style parameters across generations.
- Optional: Cartesia voice cloning of Tim (3-second clip → clone) for a "personalized base voice" layer.

### 8. Augmentation Depth (Gap #8)
**Current state**: Single round.  
**Best practice**: Multiple rounds + realistic far-field simulation (RIR + SNR noise) are standard in OWW eval protocols.

**Proposed refinement**:
- Set `augmentation_rounds: 2` (or more if wall-time allows).
- Include gain, noise overlay, and RIR in every round with randomized parameters.

### 9. Verifier Model (Gap #9)
**Current state**: Noted as "may be overkill".  
**Best practice (OWW docs/custom_verifier_models.md)**: Lightweight logistic-regression verifier (trained on ~3 positive + ~10s negative clips from Tim) sits on top of the base model and slashes false positives for single-user scenarios. Extremely cheap to add.

**Proposed refinement**:
- Make this a standard post-training step for home deployment (single-user).
- Train on Tim’s real clips only; apply with `custom_verifier_threshold=0.3`.

### 10. Model Iteration Loop (Gap #10)
**Current state**: One-shot.  
**Best practice**: Explicit iteration is the norm—train → deploy → collect real FPs/FNs → augment adversarial/real data → retrain.

**Proposed refinement**:
- Formalize as a 2–3 iteration cycle:
  1. Base synthetic + real-voice run.
  2. Deploy → collect 15–30 min false-positive logs on Pi.
  3. Add those as new adversarial negatives → retrain.
- Target convergence at target_false_positives_per_hour ≤0.5 with acceptable FRR.

### Summary of Mutated High-Level Pipeline
- **Positive samples**: 10k+ Cartesia (multi-voice, high prosody variation) + 10–20% real Tim clips.
- **Adversarial**: Expanded phonetic set, same scale/quality.
- **Negatives**: ACAV100M + RIR (HF auto-download) + realistic SNR.
- **Training**: `augmentation_rounds=2`, higher steps if needed, optional verifier.
- **Validation**: Systematic on-device FAR/FRR + iteration loop.
- **Compute**: Still fits g4dn.xlarge; wall time scales linearly with sample count but remains cheap.

This keeps the methodology lightweight while closing every identified gap. Cartesia remains the core TTS engine—its superiority for clean, controllable synthetic data is fully leveraged.

Next steps I recommend:
- Project specialist: Incorporate these into an updated "Target State" draft.
- Or tell me to deep-dive any area (e.g., exact Cartesia parameter mapping, phonetic expansion script ideas, or example YAML diffs from automatic_model_training.ipynb).

Ready for your mediation turn!