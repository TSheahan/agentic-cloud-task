"""Shim for openwakeword.train import path.

Upstream ``train.py`` always executes ``from generate_samples import generate_samples``
using ``piper_sample_generator_path`` from the YAML. When the happy path omits
``--generate_clips`` and WAVs are pre-placed (e.g. Cartesia), that function is
never called — only this module must import cleanly.

If generation is mistakenly requested against this shim, fail loudly; use
Appendix A (deprecated Piper) in oww-training-env.profile.md for Piper TTS.
"""


def generate_samples(*args, **kwargs):
    raise RuntimeError(
        "generate_samples() was called but this profile's happy path uses "
        "pre-placed WAVs and omits --generate_clips. "
        "For Piper TTS generation, see Appendix A (deprecated fallback) in "
        "oww-training-env.profile.md."
    )
