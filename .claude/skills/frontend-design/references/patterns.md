# Patterns Reference

## Contents
- Design Consistency Patterns
- Component Composition
- Data Display Patterns
- Empty States
- WARNING: Hardcoded Colors
- WARNING: Missing data-testid
- Visual Differentiation Checklist

## Design Consistency Patterns

### Revenue Numbers

Always monospaced, always color-coded:

```jsx
// Positive revenue
<span className="font-mono font-medium text-2xl text-emerald-400">$2,450.00</span>

// Negative/lost revenue
<span className="font-mono font-medium text-2xl text-red-400">-$180.00</span>

// Neutral/total
<span className="font-mono font-medium text-2xl">$12,800.00</span>
```

### Labels

Uppercase mono for data labels creates a strong typographic hierarchy:

```jsx
<span className="font-mono text-xs uppercase tracking-wider text-muted-foreground">
  TOTAL REVENUE
</span>
```

### Icon + Text Pairs

Icons from lucide-react only. Consistent sizing within context:

```jsx
// In navigation (medium)
<item.icon className="w-5 h-5" />

// In stat cards (large, with colored background)
<div className="bg-emerald-500/10 p-3 rounded-lg">
  <DollarSign className="w-6 h-6 text-emerald-400" />
</div>

// In table cells (small)
<Phone className="w-4 h-4 text-muted-foreground" />
```

## Component Composition

### Page Structure Formula

Every page follows this skeleton:

```jsx
<Layout title="Page Name">
  <div className="space-y-6">
    {/* 1. Header: title + actions */}
    <div className="flex items-center justify-between">
      <h2 className="font-heading font-semibold text-2xl">Section</h2>
      <Button size="sm">Action</Button>
    </div>

    {/* 2. Filters (optional) */}
    <div className="flex flex-wrap items-center gap-3">
      {/* Select, DatePicker, Search */}
    </div>

    {/* 3. Content: grid or table */}
    <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-6">
      {/* Cards */}
    </div>

    {/* 4. Pagination (optional) */}
    <div className="flex items-center justify-between">
      <span className="text-sm text-muted-foreground">Showing 1-20 of 45</span>
      <div className="flex gap-2">
        <Button variant="outline" size="sm"><ChevronLeft /></Button>
        <Button variant="outline" size="sm"><ChevronRight /></Button>
      </div>
    </div>
  </div>
</Layout>
```

### Stat Card Array Pattern

Define stats as data, render uniformly:

```jsx
const stats = [
  { title: "Revenue", value: formatCurrency(data.revenue), icon: DollarSign, color: "text-emerald-400", bg: "bg-emerald-500/10" },
  { title: "Appointments", value: data.total, icon: Calendar, color: "text-blue-400", bg: "bg-blue-500/10" },
  { title: "No-Shows", value: data.no_shows, icon: AlertTriangle, color: "text-red-400", bg: "bg-red-500/10" },
  { title: "Waitlist", value: data.waitlist, icon: Users, color: "text-primary", bg: "bg-primary/10" },
];

<div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-6">
  {stats.map(s => (
    <Card key={s.title} className="hover:border-primary/50 transition-colors duration-300">
      <CardContent className="p-6">
        <div className="flex items-center justify-between">
          <div>
            <p className="text-sm text-muted-foreground">{s.title}</p>
            <p className={`font-mono font-medium text-2xl ${s.color}`}>{s.value}</p>
          </div>
          <div className={`${s.bg} p-3 rounded-lg`}>
            <s.icon className={`w-6 h-6 ${s.color}`} />
          </div>
        </div>
      </CardContent>
    </Card>
  ))}
</div>
```

## Data Display Patterns

### Date Formatting

Use `date-fns` for all date formatting:

```jsx
import { format } from "date-fns";

// In tables
format(new Date(appointment.date), "MMM d, yyyy");  // "Jan 15, 2026"

// In chat — relative time
const formatMessageTime = (timestamp) => {
  const date = new Date(timestamp);
  const diffDays = Math.floor((Date.now() - date) / 86400000);
  if (diffDays === 0) return format(date, "h:mm a");
  if (diffDays === 1) return "Yesterday";
  if (diffDays < 7) return format(date, "EEEE");
  return format(date, "MMM d");
};
```

### Pagination

```jsx
const [page, setPage] = useState(1);
const limit = 20;

// Fetch with pagination
const res = await axios.get(`${API}/appointments?page=${page}&limit=${limit}`);

// Display
<p className="text-sm text-muted-foreground">
  Showing {(page - 1) * limit + 1} to {Math.min(page * limit, total)} of {total}
</p>
```

## Empty States

When a list or table has no data:

```jsx
// DO — helpful empty state with icon and explanation
<div className="text-center py-12">
  <Users className="w-12 h-12 text-muted-foreground mx-auto mb-4" />
  <h3 className="font-heading text-lg font-semibold mb-2">No clients yet</h3>
  <p className="text-sm text-muted-foreground">
    Clients will appear here after their first SMS interaction
  </p>
</div>

// DON'T — bare text with no visual weight
{clients.length === 0 && <p>No data</p>}
```

## WARNING: Hardcoded Colors

**The Problem:**

```jsx
// BAD — bypasses the CSS variable system
<div className="bg-zinc-900 border-zinc-700 text-zinc-300">
```

**Why This Breaks:**
1. Won't respond to theme variable changes
2. Creates subtle color mismatches (zinc-900 vs card which is #18181b)
3. Developers copy-paste these and the inconsistency spreads

**The Fix:**

```jsx
// GOOD — uses design system tokens
<div className="bg-card border-border text-muted-foreground">
```

**Exception:** Status colors (`emerald-400`, `red-400`, etc.) are intentionally hardcoded because they represent fixed semantic meaning that shouldn't change with theme.

## WARNING: Missing data-testid

**The Problem:**

```jsx
// BAD — no test hook
<Button onClick={handleSave}>Save</Button>
```

**Why This Breaks:**
1. The `design_guidelines.json` requires `data-testid` on ALL interactive elements
2. E2E tests can't reliably target elements without them
3. Refactoring class names or text breaks test selectors

**The Fix:**

```jsx
// GOOD — always add data-testid
<Button onClick={handleSave} data-testid="save-settings-btn">Save</Button>
<Input data-testid="client-search" placeholder="Search..." />
<Select data-testid="status-filter">
```

## Visual Differentiation Checklist

Before shipping any new UI, verify:

- [ ] Gold accent used for primary action only (not decoration)
- [ ] Playfair Display on headings, Inter on body, JetBrains Mono on numbers
- [ ] Status colors follow the 8-state map (no inventing new status colors)
- [ ] Cards have `hover:border-primary/50` hover effect
- [ ] No gradients on backgrounds (solid dark colors only)
- [ ] Revenue numbers are `font-mono font-medium` with color coding
- [ ] All interactive elements have `data-testid`
- [ ] Icons are from lucide-react (not heroicons, not font-awesome)
- [ ] Toasts use Sonner (`toast.success`/`toast.error`) not alerts
- [ ] Loading states use pulse skeletons, not spinners
