# Model Routing Rules

AI-OS uses multiple models **serially**, not in parallel.

Context lives in files.
Models are interchangeable tools.

---

## CODER
Role:
- Code implementation
- Refactoring
- Boilerplate generation

Rules:
- No architectural changes
- No math assumptions
- Follow DESIGN_DECISIONS.md strictly

---

## REASONER
Role:
- Logic validation
- Mathematical checks
- Risk identification

Rules:
- Do not write code
- Do not optimize prematurely
- Identify problems, not solutions

---

## REVIEWER (Cloud or Alternate Model)
Role:
- Architecture critique
- Cross-file coherence
- Blind-spot detection

Rules:
- Read-only
- No commits
- High-level feedback only

---

## Global Rules
- One model active at a time
- Always re-read CONTEXT.md
- If constraints conflict, stop and ask
