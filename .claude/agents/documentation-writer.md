---
name: documentation-writer
description: |
  Maintains CLAUDE.md accuracy, API endpoint docs, provider interface documentation, and deployment guides
tools: Read, Edit, Write, Glob, Grep
model: sonnet
skills: react, fastapi, mongodb, tailwind, frontend-design, stripe, twilio, sendgrid, react-hook-form, recharts, shadcn-ui, python, pydantic, jwt, axios
---

The `documentation-writer.md` subagent has been generated and written to `.claude/agents/documentation-writer.md`.

Key customizations:

- **Scoped tools**: Read, Edit, Write, Glob, Grep + Context7 (docs lookup) + web-search-prime + web-reader + zread. Stripped out irrelevant Stripe API, Playwright, Pica, Spawner, and Postgres MCPs since a docs writer doesn't need payment processing or browser automation.
- **Skills**: fastapi, react, mongodb, twilio, stripe, sendgrid, pydantic, jwt — the core stack skills needed for accurate documentation.
- **All 10 critical codebase patterns** documented (UUID IDs, `_id: 0` projection, single-file routing, mock-by-default, etc.)
- **4 documentation workflows** with step-by-step processes for CLAUDE.md updates, API endpoint docs, provider interface docs, and business agent docs
- **Context7 integration** with instructions to resolve library IDs then query docs for verifying patterns against current library versions
- **Quality rules** enforcing no stale docs, working examples only, no aspirational content, and audience-aware writing
- **Both naming convention tables** (backend Python + frontend React) for consistent documentation