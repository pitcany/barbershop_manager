---
name: tailwind
description: |
  Applies Tailwind CSS utility classes with CSS variable theming and shadcn/ui dark theme conventions.
  Use when: writing or modifying JSX className attributes, adding new components, updating the design system, working with the dark theme, or debugging styling issues in this React + Tailwind + shadcn/ui codebase.
allowed-tools: Read, Edit, Write, Glob, Grep, Bash, mcp__plugin_context7-plugin_context7__resolve-library-id, mcp__plugin_context7-plugin_context7__query-docs, mcp__plugin_playwright_playwright__browser_take_screenshot, mcp__plugin_playwright_playwright__browser_snapshot
---

# Tailwind CSS — Barbershop Autopilot

Dark-themed Tailwind 3.x project using **CSS variables** (HSL) for all colors, **shadcn/ui** components with `cn()` merging, and three custom font families. Every color in the config resolves through `hsl(var(--token))` — NEVER use raw hex/rgb values in className.

## Critical Files

| File | Purpose |
|------|---------|
| `frontend/src/index.css` | CSS variable definitions, `@layer base/utilities`, custom classes |
| `frontend/tailwind.config.js` | Theme extension, colors mapped to CSS vars, `tailwindcss-animate` plugin |
| `frontend/src/lib/utils.js` | `cn()` — merges classes via `clsx` + `tailwind-merge` |
| `design_guidelines.json` | Canonical component class strings, typography, layout grids |

## Color System

All colors use semantic tokens. The HSL values live in `index.css :root`:

```jsx
// GOOD — semantic token
<div className="bg-card text-card-foreground border-border" />

// BAD — raw hex bypasses theming
<div className="bg-[#18181b] text-[#fafafa] border-[#27272a]" />
```

| Token | Hex | Usage |
|-------|-----|-------|
| `primary` | #D4AF37 (gold) | CTAs, active states, ring focus |
| `background` | #09090b | Page background |
| `card` | #18181b | Card/panel surfaces |
| `muted` | #27272a | Disabled, secondary surfaces |
| `muted-foreground` | #a1a1aa | Secondary text, labels |
| `destructive` | #7f1d1d | Delete actions, errors |

Opacity modifiers work: `bg-primary/10`, `hover:bg-primary/90`, `border-primary/50`.

## Typography

Three custom font utilities defined in `@layer utilities` in `index.css`:

```jsx
<h1 className="font-heading text-3xl font-bold tracking-tight">Dashboard</h1>
<p className="text-sm text-muted-foreground">Body text</p>
<span className="font-mono font-medium text-2xl">$1,234.00</span>
```

- `font-heading` → Playfair Display (headings only)
- `font-body` → Inter (default on `body`)
- `font-mono` → JetBrains Mono (revenue numbers, labels, code)

## Component Class Patterns

Use `cn()` for all shadcn/ui component className merging. See the **shadcn-ui** skill.

```jsx
import { cn } from "@/lib/utils";

<Card className={cn("bg-card border-border", isActive && "border-primary/50")} />
```

### Cards (canonical pattern from `design_guidelines.json`)

```jsx
<Card className="bg-card border-border hover:border-primary/50 transition-colors duration-300">
  <CardContent className="p-6">
    <p className="text-sm text-muted-foreground mb-1">{label}</p>
    <p className="font-mono font-medium text-2xl">{value}</p>
  </CardContent>
</Card>
```

### Layout Grids

```jsx
// Dashboard stat cards
<div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-6">

// Generic card grid
<div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-6">

// Page container
<div className="p-6 lg:p-8">
```

## Custom Classes

Defined in `index.css` beyond standard Tailwind:

```css
/* Chat bubbles */
.chat-bubble-inbound  → bg-secondary text-foreground rounded-2xl rounded-bl-sm
.chat-bubble-outbound → bg-primary text-primary-foreground rounded-2xl rounded-br-sm

/* Loading animation */
.animate-pulse-gold   → gold-tinted pulse (2s cubic-bezier)
```

## Anti-Patterns

### WARNING: Raw Color Values

NEVER use hex, rgb, or arbitrary color values. They break theme consistency and won't update if the design system changes.

```jsx
// BAD
<div className="bg-[#D4AF37] text-white" />

// GOOD
<div className="bg-primary text-primary-foreground" />
```

### WARNING: `transition-all`

Per `design_guidelines.json`: "Do not use 'transition: all'. Animate specific properties."

```jsx
// BAD — animates everything, causes layout jank
<div className="transition-all" />

// GOOD — animate only what changes
<div className="transition-colors duration-300" />
```

## See Also

- [patterns](references/patterns.md) — DO/DON'T pairs, spacing, responsive
- [workflows](references/workflows.md) — adding components, custom classes, debugging

## Related Skills

- See the **shadcn-ui** skill for component primitives and `cn()` usage
- See the **frontend-design** skill for layout and visual design decisions
- See the **react** skill for JSX and component architecture
- See the **recharts** skill for chart color tokens (`chart-1` through `chart-5`)