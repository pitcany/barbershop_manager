# Tailwind Patterns Reference

## Contents
- Semantic Color Tokens
- Typography Patterns
- Spacing and Layout
- Interactive States
- Responsive Patterns
- Anti-Patterns

## Semantic Color Tokens

Every color in this project routes through CSS variables. The `tailwind.config.js` maps tokens to `hsl(var(--token))`.

```jsx
// Surface hierarchy (darkest to lightest)
<div className="bg-background" />    // #09090b — page
<div className="bg-card" />          // #18181b — panels
<div className="bg-secondary" />     // #27272a — elevated surfaces
<div className="bg-muted" />         // #27272a — disabled/subtle (same as secondary)
```

### Opacity Modifiers

Tailwind's `/` opacity syntax works with CSS variable colors in this config:

```jsx
// Primary with opacity — used heavily for subtle highlights
<div className="bg-primary/10" />     // Gold tint for icon backgrounds
<div className="hover:bg-primary/90" /> // Slightly dimmed on hover
<div className="border-primary/50" />  // Subtle gold border on active cards
<div className="bg-accent/50" />       // Half-opacity accent for hover states
```

### WARNING: Using `emerald`, `red`, etc. Directly

Some pages (DashboardPage) use `text-emerald-400` and `bg-red-500` for status-specific colors. These are exceptions — prefer semantic tokens for anything theme-dependent.

```jsx
// Acceptable for semantic status only
<span className="text-emerald-400">$1,234</span>  // revenue positive
<div className="bg-red-500 rounded-full" />        // chart legend dot

// BAD for general UI — use tokens
<button className="bg-blue-500" />  // breaks theme
<button className="bg-primary" />   // correct
```

## Typography Patterns

Three font families, applied via custom utilities in `index.css`:

```jsx
// Page titles — ALWAYS font-heading
<h1 className="font-heading text-3xl font-bold tracking-tight">
  {pageTitle}
</h1>

// Section titles
<CardTitle className="font-heading text-xl">{title}</CardTitle>

// Body/descriptions — font-body is default, no class needed
<p className="text-sm text-muted-foreground mb-1">{description}</p>

// Numbers and data — ALWAYS font-mono
<p className="font-mono font-medium text-2xl">{formattedAmount}</p>

// Labels (uppercase micro text)
<span className="font-mono text-xs uppercase tracking-wider text-muted-foreground">
  {label}
</span>
```

### WARNING: Heading Font on Body Text

`font-heading` (Playfair Display) is a display serif. Using it on small body text looks wrong and hurts readability.

```jsx
// BAD — serif at small sizes
<p className="font-heading text-sm">{description}</p>

// GOOD — Inter (default) for body
<p className="text-sm text-muted-foreground">{description}</p>
```

## Spacing and Layout

Consistent spacing from `design_guidelines.json`:

```jsx
// Page container (from Layout.jsx)
<div className="p-6 lg:p-8">{children}</div>

// Section spacing
<div className="space-y-8">{sections}</div>

// Component-level spacing
<div className="space-y-4">{formFields}</div>
<div className="gap-6">{gridItems}</div>

// Card internal padding
<CardContent className="p-6">{content}</CardContent>
<CardContent className="p-4">{compactContent}</CardContent>
```

### Grid Patterns

```jsx
// 4-column stat row (dashboard)
<div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-6">

// 3-column card grid
<div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-6">

// Sidebar + content (conversations)
<div className="grid grid-cols-1 lg:grid-cols-3 gap-6 h-[calc(100vh-200px)]">
```

## Interactive States

All interactive elements follow this pattern from the design system:

```jsx
// Buttons — from design_guidelines.json
className="bg-primary text-primary-foreground hover:bg-primary/90 shadow-sm font-medium transition-all active:scale-95"

// Cards — hover reveals gold border
className="bg-card border-border hover:border-primary/50 transition-colors duration-300"

// Sidebar links
// Active:
className="bg-primary/10 text-primary border-r-2 border-primary"
// Inactive:
className="text-muted-foreground hover:text-foreground hover:bg-accent/50"

// Inputs
className="bg-input/50 border-input focus:ring-1 focus:ring-primary focus:border-primary transition-all"
```

### WARNING: Missing `data-testid`

Per project guidelines: "All interactive elements MUST have a `data-testid` attribute."

```jsx
// BAD — missing testid
<Button onClick={handleSave}>Save</Button>

// GOOD
<Button onClick={handleSave} data-testid="save-button">Save</Button>
```

## Responsive Patterns

This project uses mobile-first with `lg:` as the primary breakpoint for sidebar/content layouts:

```jsx
// Mobile overlay + desktop sidebar (Layout.jsx)
<aside className={`
  fixed inset-y-0 left-0 z-50 w-64 bg-card border-r border-border
  transform transition-transform duration-200 ease-in-out
  ${sidebarOpen ? 'translate-x-0' : '-translate-x-full'}
  lg:translate-x-0 lg:static lg:transform-none
`}>

// Mobile header (hidden on desktop)
<header className="lg:hidden sticky top-0 z-30 bg-background/95 backdrop-blur border-b border-border p-4">
```

### Glassmorphism (Mobile Header)

```jsx
// Sticky header with blur effect
className="bg-background/95 backdrop-blur border-b border-border/50"
```

## Anti-Patterns

### WARNING: Gradients

Per design guidelines: "Do not use gradients for backgrounds, stick to solid dark colors."

```jsx
// BAD
<div className="bg-gradient-to-r from-primary to-yellow-600" />

// GOOD — solid color or opacity variant
<div className="bg-primary" />
<div className="bg-primary/10" />
```

### WARNING: String Concatenation Instead of `cn()`

When conditionally applying classes, always use `cn()` from `@/lib/utils`. Raw string concatenation causes class conflicts that `tailwind-merge` resolves.

```jsx
// BAD — conflicting classes won't resolve
<div className={`p-4 ${isLarge ? 'p-8' : ''}`} />

// GOOD — tailwind-merge handles conflicts
<div className={cn("p-4", isLarge && "p-8")} />
```

See the **shadcn-ui** skill for `cn()` usage with component variants.