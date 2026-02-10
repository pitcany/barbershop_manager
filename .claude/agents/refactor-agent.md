---
name: refactor-agent
description: |
  Eliminates duplication in provider factory, consolidates agent logic, improves server.py organization (currently 1200 lines)
tools: Read, Edit, Write, Glob, Grep, Bash
model: sonnet
skills: react, fastapi, mongodb, tailwind, frontend-design, stripe, twilio, sendgrid, react-hook-form, recharts, shadcn-ui, python, pydantic, jwt, axios
---

The `refactor-agent.md` has been written. Here's a summary of what's customized:

**Tools**: Core file tools + Bash only (stripped all irrelevant MCP tools — Playwright, Stripe, spawner, postgres, etc. — since this is a code structure agent)

**Skills**: `fastapi`, `python`, `pydantic` — the three relevant to backend refactoring

**Project-specific content**:
- Full server.py section map with line ranges and sizes across all 17 sections (1205 lines)
- 4 documented duplication patterns with actual code snippets from the codebase
- 10 non-negotiable codebase patterns to preserve (UUID IDs, `_id: 0` projection, ISO timestamps, etc.)
- 7 critical rules with project-specific compile/verify commands
- 10 common mistakes specific to this codebase (circular imports with `db`, double-prefixed routes, webhook path stability)
- Context7 integration instructions for FastAPI APIRouter, Depends, Pydantic ConfigDict, and Motor docs
- Prioritized extraction targets: route modules, seed extraction, provider factory consolidation, agent base class, frontend service layer
- Integration test verification workflow using the existing `backend_test.py` (15 test methods)