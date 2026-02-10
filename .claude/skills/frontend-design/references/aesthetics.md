# Aesthetics Reference

## Contents
- Color System
- Typography
- Visual Identity
- Semantic Colors
- Chart Colors
- WARNING: Generic AI Aesthetics

## Color System

All colors use HSL CSS variables defined in `frontend/src/index.css`. Reference via Tailwind classes — never hardcode hex values in components.

```css
/* Core palette — index.css :root */
--background: 0 0% 3.5%;       /* #09090b near-black */
--foreground: 0 0% 98%;         /* #fafafa off-white */
--card: 0 0% 9%;                /* #18181b dark gray */
--primary: 43 74% 52%;          /* #D4AF37 gold */
--primary-foreground: 0 0% 0%;  /* black text on gold */
--muted: 0 0% 15%;              /* #27272a medium dark */
--muted-foreground: 0 0% 63%;   /* #a1a1aa light gray */
--border: 0 0% 15%;             /* #27272a subtle borders */
--ring: 43 74% 52%;             /* gold focus rings */
```

### Gold Accent Usage

Gold is the signature color. Use it deliberately:

```jsx
// GOOD — gold for primary actions, active states, focus rings
<Button className="bg-primary text-primary-foreground">Book Now</Button>
<NavLink className="bg-primary/10 text-primary border-r-2 border-primary" />
<Input className="focus:ring-1 focus:ring-primary focus:border-primary" />

// BAD — gold everywhere dilutes its impact
<div className="bg-primary p-8">  {/* Too much gold */}
  <h1 className="text-primary">   {/* Gold on gold background */}
```

### Background Layering

Three depth levels create visual hierarchy without gradients:

| Level | Class | Hex | Usage |
|-------|-------|-----|-------|
| Base | `bg-background` | #09090b | Page background |
| Surface | `bg-card` | #18181b | Cards, sidebar |
| Elevated | `bg-secondary` | #27272a | Dropdowns, chat bubbles |

## Typography

Three font families, each with a distinct role:

```jsx
// Headings — Playfair Display (serif)
<h1 className="font-heading font-bold text-4xl tracking-tight">Dashboard</h1>
<h2 className="font-heading font-semibold text-3xl tracking-tight">Revenue</h2>
<h3 className="font-heading font-semibold text-2xl">Appointments</h3>

// Body — Inter (sans-serif)
<p className="font-body text-base leading-relaxed text-muted-foreground">
  Description text here
</p>

// Numbers & Labels — JetBrains Mono
<span className="font-mono font-medium text-2xl">$2,450.00</span>
<span className="font-mono text-xs uppercase tracking-wider text-muted-foreground">
  TOTAL REVENUE
</span>
```

### WARNING: Wrong Font Usage

**The Problem:**

```jsx
// BAD — serif font on small labels looks pretentious
<span className="font-heading text-xs">status</span>

// BAD — body font on revenue numbers looks weak
<span className="font-body text-2xl">$2,450.00</span>
```

**Why This Breaks:**
1. Playfair Display is designed for large display sizes — it becomes illegible at small sizes
2. Inter lacks the tabular numerals that make financial data scannable
3. Mixing font roles creates visual confusion

**The Fix:**

```jsx
// GOOD — mono for numbers, heading for titles, body for everything else
<span className="font-mono font-medium text-2xl text-emerald-400">$2,450.00</span>
<h2 className="font-heading font-semibold text-2xl">Monthly Revenue</h2>
<p className="text-sm text-muted-foreground">Last 30 days</p>
```

## Semantic Colors

Status indicators use translucent background + vivid foreground:

```jsx
const SEMANTIC = {
  success:  "bg-emerald-500/20 text-emerald-400",  // confirmed, paid, positive
  warning:  "bg-yellow-500/20 text-yellow-400",     // pending, needs attention
  error:    "bg-red-500/20 text-red-400",           // cancelled, no-show, negative
  info:     "bg-blue-500/20 text-blue-400",         // completed, informational
  alert:    "bg-orange-500/20 text-orange-400",     // deposit pending
  special:  "bg-purple-500/20 text-purple-400",     // rescheduled
};
```

The `/20` opacity on backgrounds keeps badges readable against the dark card surface without competing with the gold primary.

## Chart Colors

Defined as CSS variables for **recharts**. See the **recharts** skill for implementation.

```css
--chart-1: 43 74% 52%;   /* Gold — primary metric */
--chart-2: 142 72% 29%;  /* Green — recovered revenue */
--chart-3: 0 72% 51%;    /* Red — lost revenue */
--chart-4: 221 83% 53%;  /* Blue — informational */
--chart-5: 262 83% 58%;  /* Purple — secondary */
```

When building charts, use hardcoded hex in Recharts components (it doesn't read CSS variables):

```jsx
<Area stroke="#10b981" fill="url(#greenGradient)" />  // Recovered
<Area stroke="#ef4444" fill="url(#redGradient)" />     // Lost
```

## WARNING: Generic AI Aesthetics

**The Problem:**

```jsx
// BAD — every AI-generated dashboard looks like this
<div className="bg-gradient-to-r from-purple-500 to-blue-500 rounded-xl p-6">
  <h1 className="font-sans text-white">Dashboard</h1>
</div>
```

**Why This Breaks:**
1. Purple/blue gradients are the "AI default" — instantly recognizable as generic
2. Gradients conflict with the project's matte dark aesthetic
3. Sans-serif headings lose the barbershop personality

**The Fix:**

```jsx
// GOOD — matches project identity
<Card className="hover:border-primary/50 transition-colors duration-300">
  <CardHeader>
    <CardTitle className="font-heading font-semibold text-2xl">Dashboard</CardTitle>
  </CardHeader>
</Card>
```

**When You Might Be Tempted:** When building hero sections, onboarding screens, or empty states. Resist gradients — use the gold accent sparingly on borders and text instead.
