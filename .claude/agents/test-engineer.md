---
name: test-engineer
description: |
  Writes tests for SMS compliance, appointment workflows, provider mocking, and API integration testing
tools: Read, Edit, Write, Glob, Grep, Bash
model: sonnet
skills: react, fastapi, mongodb, tailwind, frontend-design, stripe, twilio, sendgrid, react-hook-form, recharts, shadcn-ui, python, pydantic, jwt, axios
---

The test-engineer subagent has been written to `.claude/agents/test-engineer.md`. Here's what was customized:

**Skills selected**: `fastapi, python, pydantic, twilio, stripe, jwt` — the backend-relevant skills for writing tests against the API, models, SMS compliance, and payment flows.

**MCP tools scoped** to what a test engineer needs:
- **Context7** for looking up pytest/FastAPI/httpx/Pydantic docs
- **web-search-prime** for researching testing patterns
- **Playwright** for E2E browser tests against the admin dashboard
- Stripped out Stripe API, Pica, Spawner, Postgres, zread, and zai-mcp-server tools (not needed for testing)

**Project-specific content**:
- 3-layer testing strategy: unit tests (SMS compliance, agents, audit, revenue logger, models) → integration tests (FastAPI endpoints via httpx) → E2E (Playwright)
- Mock patterns using actual project code: `MockSMSProvider`, `AsyncMock` for Motor DB, `httpx.AsyncClient` with ASGI transport
- All 10 critical rules enforcing project conventions (UUID string IDs, ISO timestamps, `{"_id": 0}` projection, `extra="ignore"`, non-blocking audit, mock-by-default providers)
- SMS compliance checklist with the exact `OPT_OUT_KEYWORDS` and consent field names
- Appointment status machine with all 8 states and valid transitions
- Test file organization plan mapping test files to source modules
- Context7 workflow instructions for documentation lookups