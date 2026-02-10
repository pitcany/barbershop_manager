# Recharts Patterns Reference

## Contents
- Dark Theme Styling
- Gradient Fill Pattern
- Axis Formatting
- Tooltip Customization
- ResponsiveContainer Usage
- Data Shape Conventions
- Anti-Patterns

## Dark Theme Styling

Every Recharts component must be explicitly styled for dark backgrounds. Recharts defaults to white/light colors that are invisible on `#09090b`.

```jsx
// GOOD — explicit dark theme colors on every element
<CartesianGrid strokeDasharray="3 3" stroke="#27272a" />
<XAxis dataKey="date" stroke="#a1a1aa" tick={{ fill: '#a1a1aa', fontSize: 12 }} />
<YAxis stroke="#a1a1aa" tick={{ fill: '#a1a1aa', fontSize: 12 }} />
```

```jsx
// BAD — missing stroke/fill overrides, invisible on dark background
<CartesianGrid />
<XAxis dataKey="date" />
<YAxis />
```

**Why this matters:** Recharts inherits no CSS variables from Tailwind. Every text fill, stroke, and background must be set via props. Forgetting even one produces invisible or barely-visible elements.

## Gradient Fill Pattern

The project uses SVG `<linearGradient>` inside `<defs>` for area charts. This creates a fade-to-transparent effect that looks clean on dark backgrounds.

```jsx
<AreaChart data={data}>
  <defs>
    <linearGradient id="colorRevenue" x1="0" y1="0" x2="0" y2="1">
      <stop offset="5%" stopColor="#D4AF37" stopOpacity={0.3} />
      <stop offset="95%" stopColor="#D4AF37" stopOpacity={0} />
    </linearGradient>
  </defs>
  <Area type="monotone" dataKey="revenue"
    stroke="#D4AF37" fillOpacity={1} fill="url(#colorRevenue)" />
</AreaChart>
```

**Rules:**
- `stopOpacity` top: 0.3 (not higher — looks garish on dark bg)
- `stopOpacity` bottom: 0 (fades to transparent)
- `fillOpacity={1}` on `<Area>` — lets the gradient control opacity
- Gradient `id` must be unique per chart if multiple charts render simultaneously

### WARNING: Duplicate Gradient IDs

**The Problem:**

```jsx
// BAD — two charts on the same page with the same gradient id
<AreaChart data={data1}>
  <defs><linearGradient id="color1">...</linearGradient></defs>
  <Area fill="url(#color1)" />
</AreaChart>

<AreaChart data={data2}>
  <defs><linearGradient id="color1">...</linearGradient></defs>
  <Area fill="url(#color1)" />
</AreaChart>
```

**Why This Breaks:** SVG gradient IDs are global to the document. The second gradient silently overwrites the first, causing both charts to share one gradient definition.

**The Fix:** Prefix gradient IDs with chart name: `id="revenueColorGreen"`, `id="appointmentsColorBlue"`.

## Axis Formatting

### Dollar formatting on YAxis

```jsx
<YAxis
  stroke="#a1a1aa"
  tick={{ fill: '#a1a1aa', fontSize: 12 }}
  tickFormatter={(value) => `$${value}`}
/>
```

### Short date formatting on XAxis

```jsx
<XAxis
  dataKey="date"
  stroke="#a1a1aa"
  tick={{ fill: '#a1a1aa', fontSize: 12 }}
  tickFormatter={(value) => {
    const d = new Date(value);
    return `${d.getMonth() + 1}/${d.getDate()}`;
  }}
/>
```

**Note:** The backend returns ISO date strings (`"2026-02-10"`). Always parse with `new Date(value)` in formatters.

## Tooltip Customization

```jsx
<Tooltip
  contentStyle={{
    backgroundColor: '#18181b',
    border: '1px solid #27272a',
    borderRadius: '8px',
    color: '#fafafa'
  }}
  formatter={(value) => [`$${value.toFixed(2)}`, '']}
  labelFormatter={(label) => new Date(label).toLocaleDateString()}
/>
```

**The `formatter` signature:** `(value, name, props) => [displayValue, displayName]`. Pass empty string `''` as second element to hide the series name if the custom legend already shows it.

### WARNING: Default Tooltip on Dark Theme

**The Problem:** Omitting `contentStyle` renders a white tooltip box on a dark page — jarring and unreadable.

**The Fix:** Always pass `contentStyle` matching the Card component colors from the **tailwind** skill: background `#18181b`, border `#27272a`, text `#fafafa`.

## ResponsiveContainer Usage

```jsx
// GOOD — fixed-height parent, 100% dimensions
<div className="h-72">
  <ResponsiveContainer width="100%" height="100%">
    <AreaChart data={data}>...</AreaChart>
  </ResponsiveContainer>
</div>
```

### WARNING: ResponsiveContainer with Zero Height

**The Problem:**

```jsx
// BAD — no height constraint on parent
<div>
  <ResponsiveContainer width="100%" height="100%">
    <AreaChart data={data}>...</AreaChart>
  </ResponsiveContainer>
</div>
```

**Why This Breaks:** `ResponsiveContainer` with `height="100%"` collapses to 0px if the parent has no explicit height. The chart renders but is invisible.

**The Fix:** Always set a Tailwind height class on the parent: `h-72` (288px), `h-80` (320px), or `h-96` (384px).

## Data Shape Conventions

Chart data in this project follows a flat array of objects pattern:

```javascript
// Revenue chart data from /api/dashboard/revenue-chart
[
  { date: "2026-02-01", recovered: 120.00, lost: 45.00 },
  { date: "2026-02-02", recovered: 85.50, lost: 0 },
]
```

**Rules:**
- `dataKey` on XAxis/Area/Line must match exact object keys
- Numeric values should be floats (not strings) — Recharts needs numbers for scaling
- Backend returns `{ data: [...] }` — access via `res.data.data`
- Missing days should be included with zero values, not omitted (gaps break the line)