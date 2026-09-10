# JARVIS

> A local-first AI desktop agent for Windows, powered by Ollama and designed for real computer interaction.

JARVIS is a Python-based personal AI agent that can reason about user requests, select tools, execute real operations on a Windows machine, interact with applications, manage files and projects, control Spotify, use voice input/output, and maintain memory.

The project is designed around a simple principle:

**The AI should never pretend an action happened. Tools perform actions, security controls permissions, and the system reports the actual result.**

---

## Features

### Local AI Agent

- Local LLM reasoning through Ollama
- Qwen-based agent reasoning
- Tool calling and execution
- Bounded execution to prevent uncontrolled tool loops
- Explicit handling of tool failures
- Shared execution pipeline for text and voice

### Desktop Control

- Windows application launching
- Browser interaction
- URL opening
- Computer-control tools
- Terminal commands
- Screen capture
- Active-window capture
- Image analysis

### Spotify

JARVIS can control Spotify through the Spotify Web API:

- Search and play tracks
- Pause playback
- Resume playback
- Next track
- Previous track
- Current playback status
- Active-device selection
- OAuth authentication with PKCE
- Automatic token refresh
- Retry handling for transient API failures

Spotify playback control requires a compatible Spotify Premium account.

### File & Project Operations

- Read files
- Write files
- Edit files
- Search files
- List directories
- Run tests
- Compile/check projects
- Git status
- Git diff
- Git log
- Git branch operations
- Git add
- Git commit
- Git push

### Security

JARVIS does not give the language model unrestricted control over the computer.

The execution path is protected by:

- SecurityManager
- ToolRegistry
- Permission levels
- Tool risk levels
- Filesystem path validation
- Confirmation requirements
- Bounded execution
- Tool availability checks
- Explicit confirmation for sensitive operations

Actions such as Git mutations and Spotify playback controls can require explicit user confirmation.

### Memory & Knowledge

- Persistent memory support
- Memory search
- Memory updates
- Forget/clear memory operations
- File/document indexing
- Knowledge search
- Semantic search

### Voice

- Local speech-to-text
- Local text-to-speech
- Push-to-talk desktop voice interface
- Faster-Whisper support
- CPU fallback when CUDA initialization fails
- Temporary audio files cleaned after transcription

Voice is disabled by default during development so starting JARVIS does not unexpectedly activate the microphone.

---

# Architecture

JARVIS uses a layered agent architecture:

```text
                    ┌─────────────────────┐
                    │       USER          │
                    └──────────┬──────────┘
                               │
                    ┌──────────▼──────────┐
                    │  PySide6 Desktop UI │
                    │      / Voice        │
                    └──────────┬──────────┘
                               │
                    ┌──────────▼──────────┐
                    │    AgentPipeline    │
                    │ task lifecycle      │
                    │ confirmation flow   │
                    └──────────┬──────────┘
                               │
                    ┌──────────▼──────────┐
                    │       Router        │
                    └──────────┬──────────┘
                               │
                    ┌──────────▼──────────┐
                    │        Brain        │
                    │  local LLM / Qwen   │
                    │  reasoning + tools  │
                    └──────────┬──────────┘
                               │
              ┌────────────────▼────────────────┐
              │          ToolRegistry           │
              │ validation / permissions /      │
              │ availability / dispatch         │
              └────────────────┬────────────────┘
                               │
                    ┌──────────▼──────────┐
                    │   ExecutionEngine   │
                    │ bounded execution   │
                    └──────────┬──────────┘
                               │
        ┌──────────────┬───────┼────────┬──────────────┐
        │              │       │        │              │
      Files          Git    Spotify  Browser      Computer
        │              │       │        │              │
        └──────────────┴───────┴────────┴──────────────┘