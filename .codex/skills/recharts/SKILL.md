---
name: recharts
description: |
  Builds dashboard data visualizations with Recharts 3.x components, dark-themed gradients, and responsive containers for the Barbershop Autopilot admin dashboard.
  Use when: creating charts, modifying dashboard visualizations, adding new chart types, styling chart components, or formatting chart axes/tooltips.
allowed-tools: Read, Edit, Write, Glob, Grep, Bash
---

# Recharts

Recharts 3.x renders revenue visualizations in the admin dashboard. The project uses AreaChart with gradient fills on a dark background (#09090b). All chart data comes from MongoDB aggregation pipelines via FastAPI endpoints.

## Quick Start

### Dual-Area Revenue Chart (Current Pattern)

```jsx
import {
  AreaChart, Area, XAxis, YAxis, CartesianGrid,
  Tooltip, ResponsiveContainer
} from "recharts";

// Data shape from /api/dashboard/revenue-chart
// [{ date: "2026-02-10", recovered: 45.0, lost: 35.0 }, ...]

<div className="h-72">
  <ResponsiveContainer width="100%" height="100%">
    <AreaChart data={chartData} margin={{ top: 10, right: 30, left: 0, bottom: 0 }}>
      <defs>
        <linearGradient id="colorRecovered" x1="0" y1="0" x2="0" y2="1">
          <stop offset="5%" stopColor="#10b981" stopOpacity={0.3} />
          <stop offset="95%" stopColor="#10b981" stopOpacity={0} />
        </linearGradient>
      </defs>
      <CartesianGrid strokeDasharray="3 3" stroke="#27272a" />
      <XAxis dataKey="date" stroke="#a1a1aa" tick={{ fill: '#a1a1aa', fontSize: 12 }}
        tickFormatter={(v) => `${new Date(v).getMonth()+1}/${new Date(v).getDate()}`} />
      <YAxis stroke="#a1a1aa" tick={{ fill: '#a1a1aa', fontSize: 12 }}
        tickFormatter={(v) => `$${v}`} />
      <Tooltip contentStyle={{
        backgroundColor: '#18181b', border: '1px solid #27272a',
        borderRadius: '8px', color: '#fafafa'
      }} formatter={(v) => [`$${v.toFixed(2)}`, '']}
         labelFormatter={(l) => new Date(l).toLocaleDateString()} />
      <Area type="monotone" dataKey="recovered" stroke="#10b981"
        fillOpacity={1} fill="url(#colorRecovered)" name="Recovered" />
    </AreaChart>
  </ResponsiveContainer>
</div>
```

## Dark Theme Color Palette

| Element | Color | Hex |
|---------|-------|-----|
| Grid lines | zinc-800 | `#27272a` |
| Axis stroke/text | zinc-400 | `#a1a1aa` |
| Tooltip background | zinc-900 | `#18181b` |
| Tooltip border | zinc-800 | `#27272a` |
| Tooltip text | foreground | `#fafafa` |
| Positive/recovered | emerald-500 | `#10b981` |
| Negative/lost | red-500 | `#ef4444` |

CSS chart variables exist (`--chart-1` through `--chart-5` in `frontend/src/index.css`) but are currently unused by the Recharts implementation.

## Key Rules

1. **Always wrap in ResponsiveContainer** inside a fixed-height parent (`h-72`, `h-96`, etc.)
2. **Use `<defs>` gradients** for area fills — opacity 0.3 → 0 creates the project's signature look
3. **Match dark theme** — every color must contrast against `#09090b` background
4. **Format axes** — dollars on Y (`$${v}`), short dates on X (`M/D`)
5. **Style tooltips inline** — use `contentStyle` matching card colors, not default white

## Data Flow

```
MongoDB events collection
  → aggregation pipeline (group by date, sum revenue_impact)
  → GET /api/dashboard/revenue-chart?days=14
  → { data: [{ date, recovered, lost }] }
  → setChartData(res.data.data)
  → <AreaChart data={chartData}>
```

See the **react** skill for component and data fetching patterns. See the **tailwind** skill for dark theme CSS variables. See the **fastapi** skill for dashboard endpoint patterns.

## See Also

- [patterns](references/patterns.md) — Chart patterns, gradient fills, axis formatting
- [workflows](references/workflows.md) — Adding new charts, new data series, styling