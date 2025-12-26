# Design Decisions (Non-Negotiable)

This document records **why** the system is built the way it is.
Changes here require deliberate justification.

---

## Intelligence Control
- AI models assist; they do not decide
- No autonomous code execution
- Human approval is always required

---

## Local-First Principle
- System must function offline
- Cloud is optional and replaceable
- No core dependency on proprietary APIs

---

## Explicitness Over Convenience
- All math must be readable
- All heuristics must be named
- No hidden “magic behavior”

---

## Model Replaceability
- No logic tied to a specific model
- All prompts assume models may change
- Context must live in files

---

## Git as Memory
- Git history is authoritative
- No “temporary” logic without commits
- Commit messages must explain intent

---

## Performance Philosophy
- Determinism first
- Realism second
- Speed third
