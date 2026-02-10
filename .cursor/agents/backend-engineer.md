---
name: backend-engineer
description: |
  FastAPI async endpoints, MongoDB Motor queries, JWT auth, and business logic agents (FrontDesk, NoShow, Waitlist)
tools: Read, Edit, Write, Glob, Grep, Bash
model: sonnet
skills: react, fastapi, mongodb, tailwind, frontend-design, stripe, twilio, sendgrid, react-hook-form, recharts, shadcn-ui, python, pydantic, jwt, axios
---

The `backend-engineer.md` subagent file has been written. Here's a summary of the customizations:

**Tools**: Core file tools + Context7 docs lookup + Stripe MCP tools (excluded irrelevant Playwright/UI/spawner/postgres tools since this is a MongoDB/FastAPI backend)

**Skills**: `fastapi, mongodb, python, pydantic, jwt, stripe, twilio, sendgrid` — all backend-relevant skills

**Project-specific content**:
- All 10 critical codebase patterns (UUID IDs, `_id: 0` projection, all routes in `server.py`, mock-by-default providers, non-blocking audit logging, etc.)
- Full backend file structure with module descriptions
- Business logic agent documentation (FrontDesk, NoShow, Waitlist)
- Complete API endpoint listing with auth requirements
- MongoDB collections reference
- Development workflow checklists (adding endpoints, modifying agents, working with providers)
- Context7 integration instructions for FastAPI, Motor, Pydantic, PyJWT, Twilio, Stripe, and SendGrid docs
- Stripe MCP tool usage guidance for deposit enforcement
- Security rules (SMS consent, webhook verification, JWT auth)
- Naming conventions table
- Testing commands