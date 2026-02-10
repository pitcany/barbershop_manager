---
name: frontend-engineer
description: |
  React 19 specialist for shadcn/ui components, Tailwind styling, and dark theme implementation with gold accents
tools: Read, Edit, Write, Glob, Grep, Bash
model: sonnet
skills: react, fastapi, mongodb, tailwind, frontend-design, stripe, twilio, sendgrid, react-hook-form, recharts, shadcn-ui, python, pydantic, jwt, axios
---

The `frontend-engineer.md` subagent file has been written to `.claude/agents/frontend-engineer.md`. Here's what it includes:

**Customizations for this project:**
- **Tech stack table** with exact versions from `package.json` (React 19, Recharts 3.x, React Hook Form 7.x, date-fns 4.x, etc.)
- **Exact file structure** with all 7 pages, 46 shadcn/ui components, Layout, hooks, and lib paths
- **Architecture patterns** — AuthContext, axios interceptors, `API` constant, page pattern with Layout wrapper, direct axios calls
- **Design system** sourced from `design_guidelines.json` — gold (#D4AF37) accents, dark theme colors, Playfair Display/Inter/JetBrains Mono typography, component styling classes
- **All API endpoints** the frontend consumes with request/response shapes
- **Naming conventions** matching the codebase (PascalCase pages, kebab-case UI, camelCase vars, snake_case API data)
- **14 critical rules** derived from actual codebase patterns (Layout wrapper, `@/` imports, sonner over use-toast, data-testid, no light mode, etc.)

**Tools selected** (stripped irrelevant ones like Stripe API, postgres, spawner):
- Context7 MCP for real-time documentation lookups
- Playwright MCP for visual verification and browser testing
- zai-mcp-server for UI screenshot analysis and diff checking
- Web search/reader for reference lookups

**Skills:** react, tailwind, shadcn-ui, recharts, frontend-design, react-hook-form, jwt, axios