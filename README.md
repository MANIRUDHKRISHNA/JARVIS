# JARVIS

JARVIS is a Python-based personal AI assistant project scaffold designed for voice, automation, and agent workflows.

## Project structure

- `app/` - core application package
- `tests/` - test suite
- `docs/` - project documentation
- `requirements.txt` - Python dependencies

## Getting started

1. Create a virtual environment
   ```bash
   python -m venv .venv
   .venv\Scripts\activate
   ```
2. Install dependencies
   ```bash
   pip install -r requirements.txt
   ```
3. Run the app
   ```bash
   python -m app.main
   ```

## Voice and privacy

Voice is local and uses the same `AgentPipeline` as text. It defaults to
disabled at startup, so development runs never open a microphone unexpectedly.
The desktop voice button is push-to-talk. Wake-word mode requires an explicitly
configured, local acoustic wake model; JARVIS does not claim that a generic
model recognizes "JARVIS". Faster-Whisper defaults to the `base` model and
falls back to CPU/int8 if CUDA initialization fails. Temporary STT WAV files
are deleted after transcription.

The optional `openWakeWord` package is not bundled. Install it separately only
when a supported local wake model is available, then configure its actual model
paths in `app/config/settings.py`. Screenshots are captured locally into the
system temporary directory and must be treated as sensitive.

## Build

The existing PyInstaller configuration is `JARVIS.spec`. Model weights are not
packaged: Ollama and Whisper models remain externally managed. Build with:

```bash
pyinstaller JARVIS.spec
```

## Features

- Voice input/output
- Task planning and execution
- Tool integration
- Memory support
- Local desktop UI

## License

MIT
