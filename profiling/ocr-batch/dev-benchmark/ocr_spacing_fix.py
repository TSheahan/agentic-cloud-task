"""Post-process Docling `export_to_markdown()` text for spacing normalization.

Rounds 4–6 pass ``rapidocr_params={"Rec.use_space_char": True}`` into
``RapidOcrOptions`` (RapidOCR engine; Docling does not expose ``use_space_char``
as a top-level field). This module can apply extra post-export tweaks; bump
``SPACING_FIX_REVISION`` when either layer changes.
"""

from __future__ import annotations

# Bump when OCR options or post-export fix logic changes (recorded in timings.json).
SPACING_FIX_REVISION = 2


def apply_spacing_fix(markdown: str) -> str:
    """Return markdown with spacing normalization applied.

    Identity: OCR-level fix is ``Rec.use_space_char`` via ``rapidocr_params``.
    """
    if not markdown:
        return markdown
    return markdown
