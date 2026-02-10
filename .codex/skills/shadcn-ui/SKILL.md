---
name: shadcn-ui
description: |
  Implements accessible shadcn/ui components with Radix primitives, CSS variable theming, and class-variance-authority variants.
  Use when: creating or modifying UI components in frontend/src/components/ui/, composing shadcn primitives in page components, adding new shadcn components via CLI, styling with CSS variable tokens, or wiring Radix-based interactive components (Dialog, Select, DropdownMenu, Sheet).
allowed-tools: Read, Edit, Write, Glob, Grep, Bash, mcp__plugin_context7-plugin_context7__resolve-library-id, mcp__plugin_context7-plugin_context7__query-docs, mcp__web-search-prime__webSearchPrime, mcp__web-reader__webReader, mcp__zread__search_doc, mcp__zread__read_file, mcp__zread__get_repo_structure
---

# shadcn/ui Skill

This project uses **shadcn/ui New York style** with JSX (not TSX), CSS variable theming, and `@/` import aliases. 46 components live in `frontend/src/components/ui/` as kebab-case `.jsx` files. All interactive components wrap Radix primitives; simple components are styled divs. The design system enforces a dark theme with gold (#D4AF37) primary via CSS variables.

## Quick Start

### Adding a Component

```bash
cd frontend && npx shadcn@latest add [component-name]
```

Config lives at `frontend/components.json` — style: `new-york`, tsx: `false`, cssVariables: `true`, aliases resolve `@/` to `src/`.

### Using a Component in a Page

```jsx
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { DollarSign } from "lucide-react";

export default function ExamplePage() {
  return (
    <Card className="bg-card border-border hover:border-primary/50 transition-colors duration-300">
      <CardHeader>
        <CardTitle className="font-heading text-lg">Revenue</CardTitle>
      </CardHeader>
      <CardContent className="p-6">
        <p className="font-mono text-2xl text-emerald-400">$1,250</p>
        <Badge className="bg-emerald-500/20 text-emerald-400">+12%</Badge>
        <Button variant="outline" size="sm">
          <DollarSign className="w-4 h-4 mr-2" />
          View Details
        </Button>
      </CardContent>
    </Card>
  );
}
```

## Key Concepts

| Concept | Convention | Example |
|---------|-----------|---------|
| Component files | kebab-case.jsx | `dropdown-menu.jsx`, `alert-dialog.jsx` |
| Imports | `@/components/ui/` | `import { Button } from "@/components/ui/button"` |
| Class merging | `cn()` from `@/lib/utils` | `cn("base-styles", className)` |
| Variants | `cva()` from class-variance-authority | `buttonVariants({ variant: "outline", size: "sm" })` |
| Colors | CSS variable tokens only | `bg-card`, `text-foreground`, `border-border` |
| Icons | lucide-react only | `<Calendar className="w-4 h-4" />` |
| Toasts | Sonner (not Radix toast) | `toast.success("Saved")` via `sonner` |
| Fonts | CSS utility classes | `font-heading` (Playfair), `font-mono` (JetBrains) |

## Common Patterns

### Status Badge Coloring

**When:** Displaying appointment/payment status indicators.

```jsx
const statusColors = {
  confirmed: "bg-emerald-500/20 text-emerald-400",
  pending: "bg-yellow-500/20 text-yellow-400",
  cancelled: "bg-red-500/20 text-red-400",
  no_show: "bg-red-500/20 text-red-400",
};

<Badge className={statusColors[status] || "bg-secondary"}>
  {status.replace(/_/g, " ")}
</Badge>
```

Pattern: 20% opacity background + solid text color.

### Stat Card with Icon

**When:** Dashboard metric display.

```jsx
<Card className="bg-card border-border hover:border-primary/50 transition-colors duration-300">
  <CardContent className="p-6">
    <div className="flex items-center justify-between">
      <div>
        <p className="text-sm text-muted-foreground mb-1">Label</p>
        <p className="font-mono font-medium text-2xl text-emerald-400">{value}</p>
      </div>
      <div className="w-12 h-12 rounded-lg bg-emerald-500/10 flex items-center justify-center">
        <TrendingUp className="w-6 h-6 text-emerald-400" />
      </div>
    </div>
  </CardContent>
</Card>
```

### WARNING: Hardcoding Colors Instead of CSS Variables

**The Problem:**
```jsx
// BAD — bypasses theme, breaks if design tokens change
<div className="bg-zinc-900 text-white border-zinc-700">
```

**The Fix:**
```jsx
// GOOD — uses CSS variable tokens
<div className="bg-card text-foreground border-border">
```

Semantic status colors (`text-emerald-400`, `text-red-400`) are acceptable for data visualization. All structural colors must use tokens.

## See Also

- [patterns](references/patterns.md) — Component composition, Radix wrapping, variant system
- [workflows](references/workflows.md) — Adding components, form integration, testing

## Related Skills

- See the **tailwind** skill for CSS variable theming and utility class conventions
- See the **react** skill for component lifecycle, Context API, and state patterns
- See the **react-hook-form** skill for form integration with shadcn Form components
- See the **frontend-design** skill for design system guidelines and page layout