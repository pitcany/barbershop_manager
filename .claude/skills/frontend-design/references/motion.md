# Motion Reference

## Contents
- Transition Conventions
- Loading States
- Hover Effects
- Custom Animations
- Micro-Interactions
- Performance Rules
- WARNING: Transition All

## Transition Conventions

This project uses CSS transitions — no Framer Motion or animation library. Keep animations subtle and functional.

**Standard durations:**

| Duration | Usage | Example |
|----------|-------|---------|
| 150ms | Default Tailwind (button hover, focus) | `transition-colors` |
| 200ms | Navigation links, interactive elements | `transition-colors duration-200` |
| 300ms | Cards, sidebar, larger surfaces | `transition-colors duration-300` |

```jsx
// Card hover — 300ms for smooth border color shift
<Card className="hover:border-primary/50 transition-colors duration-300">

// Nav link — 200ms for snappy feedback
<NavLink className="transition-colors duration-200 hover:text-foreground">

// Button — default 150ms via Tailwind
<Button>  {/* transition-colors baked into shadcn base */}
```

## Loading States

### Pulse Skeletons

Replace content with same-shaped placeholders during fetch:

```jsx
{loading ? (
  <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-6">
    {[...Array(4)].map((_, i) => (
      <Card key={i}>
        <CardContent className="p-6">
          <div className="animate-pulse space-y-3">
            <div className="h-4 bg-muted rounded w-24" />
            <div className="h-8 bg-muted rounded w-32" />
          </div>
        </CardContent>
      </Card>
    ))}
  </div>
) : (
  <StatsGrid data={stats} />
)}
```

### Gold Pulse

Custom animation for primary-colored loading indicators:

```jsx
// Defined in index.css as animate-pulse-gold
<div className="animate-pulse-gold">
  <Scissors className="w-8 h-8 text-primary" />
</div>
```

The animation uses `cubic-bezier(0.4, 0, 0.6, 1)` over 2s for a natural pulse rhythm.

### DO/DON'T for Loading

```jsx
// DO — skeleton matches content layout
<div className="animate-pulse">
  <div className="h-4 bg-muted rounded w-24 mb-2" />
  <div className="h-8 bg-muted rounded w-32" />
</div>

// DON'T — spinner in the middle of nowhere
<div className="flex justify-center py-20">
  <div className="animate-spin w-8 h-8 border-2 border-primary border-t-transparent rounded-full" />
</div>
```

**Why:** Skeletons communicate layout structure during load, reducing perceived latency. Spinners give no spatial information and feel slower.

## Hover Effects

### Cards

```jsx
// Border highlight on hover
className="hover:border-primary/50 transition-colors duration-300"
```

### Table Rows

```jsx
// Subtle background on hover
className="hover:bg-accent/30 transition-colors"
```

### Sidebar Links

```jsx
// Color shift on hover, gold highlight when active
className="text-muted-foreground hover:text-foreground hover:bg-accent/50 transition-colors duration-200"
```

### Buttons

```jsx
// Scale feedback on click (from design_guidelines.json)
className="active:scale-95 transition-all"
```

The `active:scale-95` on buttons provides physical press feedback. Only apply to buttons, not cards or links.

## Custom Animations

### Accordion (Radix)

Defined in `frontend/tailwind.config.js`:

```css
@keyframes accordion-down {
  from { height: 0; }
  to { height: var(--radix-accordion-content-height); }
}
@keyframes accordion-up {
  from { height: var(--radix-accordion-content-height); }
  to { height: 0; }
}
```

Duration: `0.2s ease-out`. Handled by the shadcn accordion component automatically.

### Chat Auto-Scroll

```jsx
const messagesEndRef = useRef(null);

useEffect(() => {
  messagesEndRef.current?.scrollIntoView({ behavior: "smooth" });
}, [messages]);

// At end of message list
<div ref={messagesEndRef} />
```

## Micro-Interactions

### Focus Rings

Gold focus ring on all interactive elements:

```jsx
// Input focus
className="focus:ring-1 focus:ring-primary focus:border-primary"

// Button focus (from shadcn base)
className="focus-visible:outline-none focus-visible:ring-1 focus-visible:ring-ring"
```

### Opacity on Disabled

```jsx
className="disabled:pointer-events-none disabled:opacity-50"
```

### Login Background Overlay

```jsx
style={{
  backgroundImage: `linear-gradient(to bottom, rgba(9,9,11,0.85), rgba(9,9,11,0.95)), url('...')`,
  backgroundSize: "cover",
  backgroundPosition: "center",
}}
```

This is the ONE place a gradient is acceptable — it's a functional overlay darkening a background image, not a decorative gradient.

## Performance Rules

1. **Animate specific properties** — not `transition-all`
2. **Stick to compositor-friendly properties** — `opacity`, `transform`, `color`, `border-color`, `background-color`
3. **Use `will-change` sparingly** — only if you see jank on a specific animation
4. **No animation on page load** — elements should appear instantly, not fade in

## WARNING: Transition All

**The Problem:**

```jsx
// BAD — animates every CSS property including layout
<div className="transition-all duration-300 p-6 hover:p-8">
```

**Why This Breaks:**
1. Layout animations (padding, margin, width) trigger reflow — expensive
2. Animates properties you didn't intend (text color, font-size, etc.)
3. Can cause visible jank on low-end devices
4. The `design_guidelines.json` explicitly says: "Do not use `transition: all`"

**The Fix:**

```jsx
// GOOD — only animate what changes
<div className="transition-colors duration-300 hover:border-primary/50">
```

**Exception:** `active:scale-95` on buttons uses `transition-all` because `transition-transform` alone won't cover the color transition happening simultaneously. This is acceptable for small, infrequent interactions.
