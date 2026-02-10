The `python` skill is now registered and visible in the skill list. Here's a summary of what was created:

**`.claude/skills/python/`** — 5 files, 935 total lines

| File | Lines | Coverage |
|------|-------|----------|
| `SKILL.md` | 100 | Quick reference: Pydantic models, agent classes, MongoDB queries, factory functions, conventions table, cross-references to 5 related skills |
| `references/patterns.md` | 243 | Async patterns, provider abstraction (4-step guide), agent pattern, factory functions, non-blocking side effects, datetime handling, 3 anti-patterns with WARNING blocks |
| `references/types.md` | 184 | Pydantic model conventions, all 8 entity models mapped, enum usage with `.value`, request/response DTOs, provider interface types, 3 anti-patterns |
| `references/modules.md` | 155 | Full module map, dependency graph, detailed description of all 10 modules, "adding new modules" checklist with validation steps |
| `references/errors.md` | 253 | Two-tier error strategy, non-blocking pattern with real code, HTTP exceptions, provider error wrapping, 5 common pitfalls (ISO parsing, None checks, consent bypass), 3 anti-patterns |

All code examples are drawn directly from the actual codebase (`agents.py`, `revenue_logger.py`, `sms_compliance.py`, `audit.py`, `providers/`, `server.py`, `models.py`). Cross-references link to **fastapi**, **mongodb**, **stripe**, **twilio**, and **sendgrid** skills.