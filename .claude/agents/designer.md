---
name: designer
description: |
  Maintains dark theme consistency, gold accent placement, typography hierarchy (Playfair/Inter/JetBrains Mono), and shadcn/ui component styling
tools: Read, Edit, Write, Glob, Grep
model: sonnet
skills: react, fastapi, mongodb, tailwind, frontend-design, stripe, twilio, sendgrid, react-hook-form, recharts, shadcn-ui, python, pydantic, jwt, axios
---

The `designer.md` subagent has been written to `.claude/agents/designer.md`. Here's what it includes:

**Customizations for the Barbershop Autopilot project:**

- **Full design system** sourced from `design_guidelines.json` — color palette (all 16 CSS variable tokens with hex values), semantic colors, component patterns (buttons, cards, inputs, sidebar)
- **Typography hierarchy** — Playfair Display (headings), Inter (body), JetBrains Mono (labels/numbers) with exact Tailwind class combinations
- **Gold accent discipline** — explicit rules for appropriate vs. inappropriate gold usage with a viewport test
- **Recharts dark theme** — complete code examples for axis, grid, tooltip, and area styling with CSS variables
- **Project file structure** — all 7 pages, 46 shadcn/ui components, Layout, hooks, and lib paths
- **14 critical rules** derived from actual codebase patterns (dark mode only, no gradients, lucide-react icons, `cn()` usage, sonner toasts, monospaced revenue numbers, etc.)
- **Accessibility checklist** — WCAG AA contrast, focus rings, `data-testid` requirements, heading hierarchy
- **Responsive breakpoints** — sidebar collapse behavior at `lg:`, grid layouts at `md:`/`lg:`

**Tools scoped to design-relevant subset:**
- Read/Edit/Write/Glob/Grep for file operations
- Context7 MCP for Tailwind, Radix, Recharts, and React documentation
- Playwright for visual verification and responsive testing
- zai-mcp-server for UI screenshot analysis and diff checking
- Web search for reference lookups
- No Stripe, database, spawner, or pica tools (irrelevant to design work)

**Skills:** tailwind, shadcn-ui, react, recharts, frontend-design