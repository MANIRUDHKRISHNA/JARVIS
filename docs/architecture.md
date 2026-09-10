# JARVIS Architecture

## Overview

JARVIS is a layered local AI agent.

The system separates:

1. User interaction
2. Request orchestration
3. LLM reasoning
4. Capability registration
5. Security
6. Execution
7. External/local tools

This prevents the language model from becoming the direct authority over the operating system.

---

# Request Flow

```text
User
 │
 ▼
┌──────────────────────┐
│ PySide6 UI / Voice   │
└──────────┬───────────┘
           │
           ▼
┌──────────────────────┐
│ AgentPipeline        │
│                      │
│ • task lifecycle     │
│ • confirmation       │
│ • shared state       │
└──────────┬───────────┘
           │
           ▼
┌──────────────────────┐
│ Router               │
└──────────┬───────────┘
           │
           ▼
┌──────────────────────┐
│ Brain                │
│                      │
│ • LLM reasoning      │
│ • tool selection     │
│ • result handling    │
└──────────┬───────────┘
           │
           ▼
┌──────────────────────┐
│ ToolRegistry         │
│                      │
│ • validation         │
│ • availability       │
│ • permissions        │
│ • dispatch           │
└──────────┬───────────┘
           │
           ▼
┌──────────────────────┐
│ SecurityManager      │
└──────────┬───────────┘
           │
           ▼
┌──────────────────────┐
│ ExecutionEngine      │
│                      │
│ • bounded execution  │
│ • execution limits   │
│ • tool calls         │
└──────────┬───────────┘
           │
           ▼
         Tools