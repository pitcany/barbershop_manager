# Tailwind Workflows Reference

## Contents
- Adding a New Component
- Adding Custom CSS Classes
- Modifying the Color System
- Debugging Styling Issues
- Working with shadcn/ui Components

## Adding a New Component

When creating a new page or component, follow the established patterns:

### Checklist

Copy this checklist and track progress:
- [ ] Step 1: Check `design_guidelines.json` for applicable component class strings
- [ ] Step 2: Use semantic color tokens (`bg-card`, `text-muted-foreground`), never raw hex
- [ ] Step 3: Apply correct typography (`font-heading` for titles, `font-mono` for numbers)
- [ ] Step 4: Add responsive breakpoints (`md:`, `lg:`) matching existing grid patterns
- [ ] Step 5: Add `data-testid` to all interactive elements
- [ ] Step 6: Use `cn()` for conditional classes, not string concatenation
- [ ] Step 7: Verify visually — gold accents on interactive states, dark surfaces, proper contrast

### Example: New Stat Card

```jsx
import { Card, CardContent } from "@/components/ui/card";
import { cn } from "@/lib/utils";
import { DollarSign } from "lucide-react";

function StatCard({ title, value, isMoney }) {
  return (
    <Card
      className="bg-card border-border hover:border-primary/50 transition-colors duration-300"
      data-testid={`stat-${title.toLowerCase().replace(/\s/g, '-')}`}
    >
      <CardContent className="p-6">
        <div className="flex items-center justify-between">
          <div>
            <p className="text-sm text-muted-foreground mb-1">{title}</p>
            <p className={cn("font-mono font-medium text-2xl", isMoney && "text-emerald-400")}>
              {value}
            </p>
          </div>
          <div className="w-12 h-12 rounded-lg bg-primary/10 flex items-center justify-center">
            <DollarSign className="w-6 h-6 text-primary" />
          </div>
        </div>
      </CardContent>
    </Card>
  );
}
```

## Adding Custom CSS Classes

Custom classes go in `frontend/src/index.css` inside `@layer utilities` or `@layer components`.

### When to Create Custom Classes

- Repeated class combinations used across multiple files (e.g., chat bubbles)
- Styles that need CSS features unavailable in Tailwind utilities (keyframes, scrollbar)
- NEVER for one-off styling — use inline Tailwind utilities instead

### How to Add

1. Open `frontend/src/index.css`
2. Add to the appropriate `@layer`:

```css
/* For reusable utility classes */
@layer utilities {
  .text-gold-gradient {
    @apply bg-clip-text text-transparent bg-gradient-to-r from-primary to-yellow-500;
  }
}

/* For component-level abstractions */
@layer components {
  .stat-card {
    @apply bg-card border-border hover:border-primary/50 transition-colors duration-300;
  }
}
```

3. Validate: `yarn start`
4. If the class doesn't apply, check that `content` in `tailwind.config.js` covers your file path

### Validation Loop

1. Add the custom class to `index.css`
2. Apply it in your component
3. Check browser devtools — class should appear in computed styles
4. If missing, verify the `@layer` is correct and restart dev server
5. Only proceed when the class renders correctly

## Modifying the Color System

Colors are defined as HSL values (without `hsl()` wrapper) in `index.css :root`:

```css
:root {
  --primary: 43 74% 52%;       /* H S% L% — no commas, no hsl() */
  --primary-foreground: 0 0% 0%;
}
```

### WARNING: HSL Format

CSS variable values are raw HSL channels, NOT full `hsl()` calls. The `hsl()` wrapper lives in `tailwind.config.js`:

```js
// tailwind.config.js wraps them:
primary: 'hsl(var(--primary))'
```

```css
/* BAD — breaks the hsl() wrapper */
--primary: hsl(43, 74%, 52%);
--primary: #D4AF37;

/* GOOD — raw channels only */
--primary: 43 74% 52%;
```

### Adding a New Color Token

1. Add the CSS variable to `index.css` `:root`
2. Add the mapping in `tailwind.config.js` under `theme.extend.colors`
3. Update `design_guidelines.json` if it's a semantic color

```css
/* index.css */
:root {
  --success: 142 72% 29%;
}
```

```js
// tailwind.config.js
colors: {
  success: 'hsl(var(--success))',
}
```

## Debugging Styling Issues

### Common Issues and Fixes

| Symptom | Cause | Fix |
|---------|-------|-----|
| Class not applying | Tailwind purged it | Check `content` paths in `tailwind.config.js` |
| Color looks wrong | Raw hex instead of token | Replace with `bg-primary`, `text-muted-foreground`, etc. |
| Hover state not visible | Missing `transition-*` | Add `transition-colors duration-300` |
| Font not loading | Missing import | Verify Google Fonts import in `index.css` line 1 |
| `cn()` not resolving conflicts | Not using `tailwind-merge` | Import `cn` from `@/lib/utils`, not building strings manually |
| Arbitrary values ignored | Bracket syntax error | Check `bg-[#hex]` format — but prefer tokens instead |

### Debugging Steps

1. Open browser devtools → Elements → Computed Styles
2. Check if the Tailwind class generated a CSS rule
3. If not present: the class was purged — check `content` paths
4. If present but overridden: check specificity — `cn()` should resolve this
5. If the color is wrong: verify `index.css` CSS variable values match `design_guidelines.json`

### Restart Requirements

These changes require a dev server restart (`yarn start`):
- Modifying `tailwind.config.js`
- Adding new `@layer` rules to `index.css`
- Changing `craco.config.js`

Regular className changes in JSX files hot-reload automatically.

## Working with shadcn/ui Components

All 46 shadcn/ui components in `frontend/src/components/ui/` use `cn()` for class merging. When overriding their styles:

```jsx
// Override default padding on CardContent
<CardContent className="p-4">  {/* shadcn default is p-6 */}

// Conditional variant on Card
<Card className={cn(
  "bg-card border-border",
  isSelected && "border-primary ring-1 ring-primary"
)} />
```

### WARNING: Don't Edit shadcn/ui Component Files for Per-Use Styling

Override via className props, don't modify the source files in `components/ui/`. Those files define base behavior — per-instance styling goes in the consuming component.

```jsx
// BAD — editing button.jsx to add gold for one page
// components/ui/button.jsx → adding special variant

// GOOD — override at usage site
<Button className="bg-primary text-primary-foreground hover:bg-primary/90">
  Gold Action
</Button>
```

See the **shadcn-ui** skill for adding new component variants when a pattern repeats across 3+ locations.

## Related Skills

- See the **shadcn-ui** skill for component API and variant patterns
- See the **react** skill for component structure and state management
- See the **frontend-design** skill for design decisions and visual guidelines
- See the **recharts** skill for chart-specific color tokens (`chart-1` through `chart-5`)