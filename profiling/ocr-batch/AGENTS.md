# profiling/ocr-batch/ — Repeatable OCR Batch

Repeatable GPU-accelerated OCR processing task.

## Characteristics

- **Instance type**: g4dn.xlarge (or appropriate GPU class)
- **AMI lifecycle**: build instance, convert to custom AMI, retain for reuse.
  Future launches boot from the custom AMI ready to work in ~90s.
- **Transfer pattern**: rsync in scripts + config → run OCR batch on GPU →
  rsync results out.
