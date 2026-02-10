---
name: data-engineer
description: |
  Designs MongoDB schemas, Motor async queries, collection indexing, and revenue/audit event tracking pipelines
tools: Read, Edit, Write, Glob, Grep, Bash
model: sonnet
skills: react, fastapi, mongodb, tailwind, frontend-design, stripe, twilio, sendgrid, react-hook-form, recharts, shadcn-ui, python, pydantic, jwt, axios
---

The `data-engineer.md` subagent has been written with the following customizations:

**Tools** (trimmed to relevant ones):
- Core file tools (Read, Edit, Write, Glob, Grep, Bash)
- Context7 MCP for Motor/PyMongo/Pydantic documentation lookup
- Web search for research
- Stripe documentation search (for payment schema questions)
- Removed all irrelevant tools: Playwright, spawner, pica, zai, zread, postgres (this project uses MongoDB, not Postgres)

**Skills**: `fastapi, mongodb, python, pydantic, stripe` — only the data-relevant ones

**Project-specific content**:
- All 13 MongoDB collections documented with primary keys and purpose
- 9 critical codebase patterns with correct/wrong code examples (UUID IDs, `_id: 0` projection, ISO timestamps, `extra="ignore"`, non-blocking logging, direct Motor usage, enum `.value`, shop_id scoping)
- Real query patterns extracted from `server.py`: pagination, aggregation pipelines, count, partial projection, message thread grouping
- Full audit & revenue logging architecture with factory functions and immutability rules
- Recommended compound indexes for the 7 most query-heavy collections
- AppointmentStatus state machine (8 states with transitions)
- Context7 integration instructions for Motor, PyMongo, Pydantic, and FastAPI docs
- Task-specific checklists for new collections, schema changes, queries, aggregations, indexes, and logging