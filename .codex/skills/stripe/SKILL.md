All three files are created. Here's a summary of what was generated:

**Created 3 files for the `stripe` skill:**

1. **`.claude/skills/stripe/SKILL.md`** (~90 lines) — Overview of the Stripe integration, quick start examples for creating payment links and handling webhooks, key concepts table mapping all relevant files, the deposit enforcement pattern, amount units warning, and links to reference files.

2. **`.claude/skills/stripe/references/patterns.md`** (~150 lines) — Provider abstraction pattern (why to never import stripe directly), payment record lifecycle with MongoDB document examples, deposit enforcement logic with the two-rule system, audit logging patterns, revenue attribution hooks, and three documented anti-patterns: hardcoding deposit amounts, converting dollars to cents before the provider, and blocking on audit/revenue logging.

3. **`.claude/skills/stripe/references/workflows.md`** (~145 lines) — End-to-end deposit collection flow (7 steps with code), webhook processing workflow with idempotency gap warning, mock payment testing workflow, step-by-step guide for adding new payment types with checklist, and a production readiness checklist with validation loop.

Key highlights:
- 18 code blocks across all files
- 3 WARNING anti-patterns documented with problem/why/fix structure
- 2 copyable checklists (new payment type, production readiness)
- 1 validation loop (production readiness)
- Cross-references to **fastapi**, **mongodb**, **pydantic**, and **python** skills
- All examples are from the actual codebase, not generic