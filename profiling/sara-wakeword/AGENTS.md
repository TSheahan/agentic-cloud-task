# profiling/sara-wakeword/ — Wake Word Training

One-shot training run for a custom OpenWakeWord model ("sara").

## Characteristics

- **Instance type**: g4dn.xlarge (or .2xlarge if needed)
- **Runtime**: ~2-4 hours on g4dn
- **Dependencies**: Python 3.10-3.11, PyTorch + CUDA, OpenWakeWord (training
  mode), synthetic TTS data generation tools, tflite/ONNX export
- **AMI lifecycle**: one-shot — AMI discarded after training completes
- **Transfer**: rsync trained model artifacts out on completion
