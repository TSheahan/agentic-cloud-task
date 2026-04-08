# Provenance: wake-word-methodology-refinement

**Session date:** Wednesday 8 April 2026

---

## Summary

Refined the "hey Sara" OpenWakeWord training methodology from a bootstrapped first-pass to a service-ready specification. The session used a structured multi-agent dialog: Tim mediated between a project agent (Cursor, responsible for project structure and methodology curation) and a search-specialist agent (Grok, responsible for OWW best-practice research).

The project agent extracted the current methodology from the sara-wakeword convergence profile and domain-knowledge documents, identifying 10 methodology gaps. Grok addressed all 10 with research-grounded recommendations across two dialog turns. The project agent reviewed each recommendation, accepting 9 mutations, deferring 2 items (Tier 2 real-voice corpus, voice cloning) as out of scope for this round, and correcting several details (adversarial phrase list curation, threshold as deployment metadata not training config).

Key decisions made:
- Sample counts scaled from 3k/500 to 10k/2k (train/test) — highest-leverage change
- Adversarial phrase set expanded from 6 to ~20 curated entries; phrases containing the wake word excluded because no one named Sara is in the deployment environment
- Voice diversity target: ≥5 Cartesia voices with prosody variation
- MIT RIRs promoted from optional to mandatory via HuggingFace automated download
- Custom verifier model (lightweight logistic regression on ~3 real clips) adopted as standard post-training step — flipped from "may be overkill" to "trivially cheap, high-value"
- 2-iteration cap established; validation protocol with FAR/FRR curve on deployment target
- Threshold explicitly designated as deployment metadata, not training config

All mutations applied to the profile (`oww-training-env.profile.md`), YAML (`hey_sara_model.yml`), and adversarial phrase file. Apply and Audit sections re-derived with stubs for new post-training steps, on the principle that the executing agent is best placed to refine them.

---

## Transcript

**User:** We're going to work towards a refined methodology for the next wake word training round in `profiling\sara-wakeword\oww-training-env.profile.md`, starting with the assumption that we have a partially suitable methodology expressed so far.

Until edit time, we can focus our attention on `Target State` because `Apply` and `Audit` sections are derived.

Methodology from the base profile is largely out of scope. It refines nvidia apt sources early, which may or may not need surfacing as a relevant detail, but otherwise simply provides the g4 platform on AWS.

Our approach will be to engage in dialog turns with a search-centric agent. You are the project agent. Your interface with the search-specialist agent is via dialog turns, mediated by me.

The objective of wake word training is to provide an OpenWakeWord model for consumption in a voice agent application. The initial bootstrapped model, showing good wake word activation, demonstrates that most of the gain is already realized. Therefore this training methodology refinement will outlay a reasonable amount of refinement effort towards the production of a service-ready model. The wake phrase is "hey sara".

You are responsible for:
- surfacing methodology (accepted) over implementation (rejected) from training delivery as described in the sara profile and the base profile.
- offering implementation feedback based on project structure
- offering feedback as reviewer of the search-specialist agent's content.
- accumulating source material for eventual re-composition and analysis towards a final report.

`scratch\sara_next` is ready as a work folder for you.

Start by setting out the current methodology.

**Assistant:** Read the sara-wakeword profile, base GPU node profile, domain-knowledge, AGENTS.md, training config YAML, smoke test script, and adversarial phrases file. Produced `scratch/sara_next/current-methodology.md` — a structured extraction of the current methodology covering pipeline architecture, sample generation strategy (positives, adversarial negatives, Tier 2 real voice, background negatives, RIRs), training configuration decisions, model validation, integration target, compute platform, and Piper deprecation. Identified 10 methodology gaps: adversarial phrase coverage, Tier 2 integration, RIR sourcing, background audio quality, threshold tuning, sample count calibration, voice diversity, augmentation depth, verifier model, and iteration loop.

**User:** Here is the first Grok (search specialist) response at: `scratch\sara_next\grok\response_1.md`.

**Assistant:** Read both the Grok response and the prompt that was sent to it. Produced `scratch/sara_next/review_1.md` — a structured per-item review. Accepted 9 mutations into a table (sample counts, adversarial expansion, voice diversity, mandatory RIRs, augmentation rounds, verifier model, iteration loop, threshold tuning). Pushed back on Tier 2 real voice as "mandatory" (demoted to planned enhancement), rejected voice cloning as out of scope, corrected threshold documentation location. Identified the custom verifier as the strongest new finding. Queued 5 follow-up questions for Grok: expanded phrase list, hyperparameter scaling, verifier API, FP target norms, background_clips vs ACAV100M pipeline roles.

**User:** Give me an assessment of how this conversation is covering off the "reasonable effort" angle so far. I know I'm coming in heavy with structure and effort. The explanation for that is that I'm seeking to ensure that the methodology becomes a solid expression of contemporary best practice, despite whatever might have been baked in at the first attempt.

**Assistant:** Assessed the process overhead as proportionate to the methodology artifact (the durable convergence profile), not to the training run itself ($2–5 on spot). The structural investment in mediated multi-agent dialog pays for itself by separating "what does OWW best practice say" from "what fits this project's constraints." Flagged that of the 5 queued questions, 2 are high-value (phrase list, verifier API) and 3 are confirmatory — the next Grok turn should aim to close the loop, not open new threads. Estimated one more Grok turn to drafting readiness.

**User:** Here is the next response: `scratch\sara_next\grok\response_2.md`

**Assistant:** Read Grok's second response covering all five questions. Produced `scratch/sara_next/review_2.md`. Key findings: accepted the concrete verifier API (train_custom_verifier, 3 clips + 10s speech); accepted steps scaling to 50k and batch_n_per_class 70; confirmed FP target 0.5 appropriate; absorbed the background_clips vs ACAV100M pipeline-stage clarification. Critically curated the adversarial phrase list — separated genuinely confusable phrases from wake-word-in-context phrases (Category C, which would suppress genuine activations) and orthographic-only variants (Category B). Proposed a curated ~20-entry list adding rhyming names (Clara, Kara, Lara, Mara, Farrah) and vowel shifts. Produced a final 14-row mutation table and declared readiness to draft the updated Target State.

**User:** I think the curation question is directly disposable by taking into account the fact that I am training this model to execute in my home, where no one named sara lives or visits.

I adopt the refinement of eliminating too-similar adversarial combinations, on the grounds that within my context they would be likely to be unprofitable, constituting a tuning customization of the model for my circumstances.

Go ahead and compose the updated target state.

**Assistant:** Composed the complete updated Target State as `scratch/sara_next/target-state-draft.md`. The draft preserved 4 unchanged sections (Instance/SSH/WORKDIR, Working directory, Python environment, Repositories), revised 3 sections (Synthetic clips with 10k counts/≥5 voices/~20 phrases, Training data with mandatory RIRs, Training config with full parameter table), and added 2 new sections (Validation protocol with FAR/FRR on deployment target, Iteration methodology with 2-iteration cap). Post-training output expanded to include the custom verifier. Included a changelog mapping each mutation to its rationale source.

**User:** Looks right. Integrate the Target State then proceed with re-derivations. remember that initial or stub derivations may be better than highly effortful or disruptive derivation efforts, because the executing agent is best placed to be the ultimate arbiter/refiner of what works.

**Assistant:** Applied all changes across three files. In `oww-training-env.profile.md`: replaced the Target State section with the refined version; updated Apply §7 (RIR download from HuggingFace, background_clips guidance), §8 (counts to 10k/2k, multi-voice note); added Apply §12 (verifier training stub) and §13 (validation protocol stub); updated Audit preamble, check 6 thresholds (10000/2000), check 13 (mandatory RIRs), added checks 16–18 (verifier, smoke test, threshold protocol as stubs). Updated `hey_sara_model.yml` with all parameter changes (n_samples, n_samples_val, steps, augmentation_rounds, batch_n_per_class, expanded custom_negative_phrases). Replaced `adversarial_phrases.example.txt` with the curated 20-phrase list.

**User:** [provenance capture request with output to scratch\sara_next]
