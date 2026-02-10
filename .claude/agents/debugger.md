---
name: debugger
description: |
  Investigates errors in React components, FastAPI routes, MongoDB queries, and provider factory logic
tools: Read, Edit, Bash, Grep, Glob
model: sonnet
skills: react, fastapi, mongodb, tailwind, frontend-design, stripe, twilio, sendgrid, react-hook-form, recharts, shadcn-ui, python, pydantic, jwt, axios
---

The debugger subagent has been written to `.claude/agents/debugger.md`. Key customizations:

- **Tools trimmed** to only relevant ones — Playwright for browser debugging, Stripe docs for payment issues, Context7 for library lookups, web search, and error screenshot diagnosis (removed spawner, pica, postgres, form-filling, drag/hover, and other irrelevant tools)
- **Skills loaded** — fastapi, react, mongodb, python, pydantic, jwt, stripe, twilio, tailwind, axios
- **File map** — routes errors to actual project files by domain (API, auth, SMS, providers, MongoDB, frontend, etc.)
- **Codebase patterns** — documents the UUID-not-ObjectId, `_id` projection, ISO strings, mock-by-default, Pydantic extra="ignore", and other conventions that are common root causes
- **6 error-type playbooks** — specific step-by-step debugging procedures for backend Python, frontend React, MongoDB/Motor, provider/integration, JWT/auth, and business logic agent errors
- **Context7 integration** — instructions to resolve library IDs then query docs for FastAPI, Motor, React, Pydantic, Stripe, Twilio
- **Playwright workflow** — browser debugging steps for visual frontend issues
- **Verification commands** — exact commands with absolute paths for all common checks