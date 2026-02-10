# Performance Reference

## Contents
- Current Performance Profile
- Memoization
- Bundle Size
- Code Splitting
- Rendering Optimization
- WARNING: Performance Anti-Patterns

## Current Performance Profile

This codebase has **no explicit performance optimizations**. No `useMemo`, `useCallback`, `React.memo`, `React.lazy`, or virtualization. For a 7-page admin dashboard with small datasets, this is appropriate.

**When to optimize:** Only when you measure a problem. React 19's automatic batching and the small component tree make premature optimization wasteful.

## Memoization

### When to Use useMemo

Only when a computation is expensive AND its inputs change rarely:

```jsx
// GOOD — Expensive computation with stable inputs
const sortedAppointments = useMemo(() =>
  [...appointments].sort((a, b) => new Date(b.scheduled_at) - new Date(a.scheduled_at)),
  [appointments]
);

// BAD — Trivial computation, useMemo adds overhead
const isActive = useMemo(() => status === "active", [status]);
```

This codebase correctly avoids useMemo for simple filters like `filteredConversations`.

### When to Use useCallback

Only when passing callbacks to memoized children:

```jsx
// Only needed if ChildComponent is wrapped in React.memo
const handleClick = useCallback(() => {
  updateStatus(id, "confirmed");
}, [id]);

<MemoizedChild onClick={handleClick} />
```

**Not needed in this codebase** — no components use `React.memo`.

### When to Use React.memo

Only for components that:
1. Render often with the same props
2. Are expensive to render (large DOM tree, heavy computation)
3. Are children of components that re-render frequently

```jsx
// Example: stat card rendered 4x, parent re-renders on any state change
const StatCard = React.memo(function StatCard({ title, value, icon: Icon }) {
  return (
    <Card className="bg-card border-border">
      <CardContent className="p-6">
        <p className="text-sm text-muted-foreground">{title}</p>
        <p className="font-mono text-2xl">{value}</p>
      </CardContent>
    </Card>
  );
});
```

## Bundle Size

### Current Dependencies (Significant)

| Package | Purpose | Size Impact |
|---------|---------|-------------|
| 26 @radix-ui packages | shadcn/ui primitives | Tree-shakeable |
| recharts | Charts | ~200KB (large) |
| date-fns | Date formatting | Tree-shakeable |
| lucide-react | Icons | Tree-shakeable |
| axios | HTTP client | ~13KB |

**recharts** is the largest dependency. If only used on DashboardPage, it's a code-splitting candidate.

### Tree-Shaking

Import only what you need:

```jsx
// GOOD — Only imports used icons
import { Calendar, DollarSign, Users } from "lucide-react";

// BAD — Would import everything (lucide-react doesn't do this, but general principle)
import * as Icons from "lucide-react";
```

## Code Splitting

Not currently implemented. If needed:

```jsx
// React.lazy for route-based splitting
const DashboardPage = React.lazy(() => import("./pages/DashboardPage"));

// Wrap in Suspense
<Suspense fallback={<LoadingSkeleton />}>
  <DashboardPage />
</Suspense>
```

**Best candidate:** DashboardPage (imports recharts, ~200KB). Lazy-loading it means users who only visit Appointments never download chart code.

## Rendering Optimization

### Skeleton Pattern Prevents Layout Shift

This codebase correctly shows skeletons that match final layout dimensions:

```jsx
// DashboardPage.jsx:52-66 — Skeleton cards match real card grid
if (loading) {
  return (
    <Layout title="Dashboard">
      <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-6">
        {[...Array(4)].map((_, i) => (
          <Card key={i} className="bg-card border-border animate-pulse">
            <CardContent className="p-6">
              <div className="h-20 bg-muted rounded" />
            </CardContent>
          </Card>
        ))}
      </div>
    </Layout>
  );
}
```

### Batched State Updates

React 18+ automatically batches state updates in event handlers and effects. This code benefits without explicit optimization:

```jsx
// These batch into one render in React 18+
setStats(statsRes.data);
setChartData(chartRes.data.data);
```

## WARNING: Performance Anti-Patterns

### WARNING: Inline Object Props on Memoized Components

**The Problem:**

```jsx
// BAD — New object reference every render, breaks React.memo
<MemoizedComponent style={{ color: "red" }} />
<MemoizedComponent data={{ items: filteredList }} />
```

**Why This Breaks:** `{ color: "red" } !== { color: "red" }` — new object created each render. React.memo sees different props and re-renders anyway.

**The Fix:**

```jsx
// GOOD — Stable reference
const style = useMemo(() => ({ color: "red" }), []);
<MemoizedComponent style={style} />
```

**Not a current issue** — this codebase doesn't use React.memo.

### WARNING: Re-fetching on Every Navigation

**The Problem:** Every page mount calls `fetchData()`. Navigating away and back triggers a full reload with loading skeleton.

**Consequence:** Perceptible flicker between pages. Acceptable for MVP, problematic at scale.

**The Fix:** React Query with `staleTime`:

```jsx
const { data } = useQuery({
  queryKey: ["appointments", statusFilter, page],
  queryFn: () => axios.get(`${API}/appointments?${params}`).then(r => r.data),
  staleTime: 30_000, // Keep data fresh for 30 seconds
});
```

### WARNING: Large List Rendering Without Virtualization

**The Problem:** AppointmentsPage renders all 20 rows per page (acceptable), but if `limit` increases or pagination is removed, rendering hundreds of `<TableRow>` elements causes jank.

**The Fix (if needed):** Use `@tanstack/react-virtual` for windowed rendering. Only render visible rows.

**Current state:** With `limit = 20`, this is a non-issue.