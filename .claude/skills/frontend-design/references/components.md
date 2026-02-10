# Components Reference

## Contents
- shadcn/ui Integration
- Card Patterns
- Form Inputs
- Tables
- Status Badges
- Chat Bubbles
- Toasts
- WARNING: Inline Styles
- WARNING: Custom Components Over shadcn

## shadcn/ui Integration

All UI primitives live in `frontend/src/components/ui/` as kebab-case JSX files. They use CVA (class-variance-authority) for variants and `cn()` for class merging. See the **shadcn-ui** skill for the full component API.

```jsx
// Standard component import pattern
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";
```

Every component uses `React.forwardRef` and accepts a `className` prop merged via `cn()`:

```jsx
// Extending a shadcn component
<Button className="w-full" variant="outline" data-testid="cancel-btn">
  Cancel
</Button>
```

## Card Patterns

Cards are the primary container. Always add hover border transition:

```jsx
// Standard data card
<Card className="hover:border-primary/50 transition-colors duration-300">
  <CardHeader className="flex flex-row items-center justify-between pb-2">
    <CardTitle className="text-sm font-medium text-muted-foreground">
      Today's Revenue
    </CardTitle>
    <DollarSign className="w-4 h-4 text-muted-foreground" />
  </CardHeader>
  <CardContent>
    <div className="font-mono font-medium text-2xl text-emerald-400">$1,250</div>
    <p className="text-xs text-muted-foreground mt-1">+12% from yesterday</p>
  </CardContent>
</Card>
```

### Card DO/DON'T

```jsx
// DO — consistent padding, semantic structure
<Card>
  <CardHeader><CardTitle>Title</CardTitle></CardHeader>
  <CardContent>Content here</CardContent>
</Card>

// DON'T — custom div replacing Card
<div className="bg-zinc-900 rounded-lg p-4 border border-zinc-700">
  <h3>Title</h3>
  <p>Content</p>
</div>
```

**Why:** Custom divs bypass the design system's CSS variable theming. When the theme changes, Card updates automatically. Hardcoded `zinc-*` colors won't.

## Form Inputs

Inputs use the `form-input` class from App.css or the shadcn Input component:

```jsx
// With icon prefix
<div className="relative">
  <Search className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-muted-foreground" />
  <Input
    placeholder="Search clients..."
    className="pl-10 bg-input/50 focus:ring-1 focus:ring-primary"
    data-testid="search-input"
  />
</div>
```

For forms with validation, see the **react-hook-form** skill. Key pattern:

```jsx
import { useForm } from "react-hook-form";
import { zodResolver } from "@hookform/resolvers/zod";
import { z } from "zod";

const schema = z.object({
  name: z.string().min(1, "Required"),
  phone: z.string().regex(/^\+?[\d\s-]{10,}$/, "Invalid phone"),
});
```

## Tables

Tables follow a consistent pattern across pages:

```jsx
<div className="rounded-lg border border-border overflow-hidden">
  <table className="w-full">
    <thead>
      <tr className="border-b border-border bg-muted/30">
        <th className="text-left p-4 text-sm font-medium text-muted-foreground">Client</th>
        <th className="text-left p-4 text-sm font-medium text-muted-foreground">Status</th>
      </tr>
    </thead>
    <tbody>
      {items.map((item) => (
        <tr key={item.id} className="border-b border-border hover:bg-accent/30 transition-colors">
          <td className="p-4 text-sm">{item.client_name}</td>
          <td className="p-4"><StatusBadge status={item.status} /></td>
        </tr>
      ))}
    </tbody>
  </table>
</div>
```

## Status Badges

Eight appointment states, each with its own color:

```jsx
const STATUS_COLORS = {
  pending:          "bg-yellow-500/20 text-yellow-400",
  confirmed:        "bg-emerald-500/20 text-emerald-400",
  deposit_pending:  "bg-orange-500/20 text-orange-400",
  deposit_paid:     "bg-emerald-500/20 text-emerald-400",
  completed:        "bg-blue-500/20 text-blue-400",
  cancelled:        "bg-red-500/20 text-red-400",
  no_show:          "bg-red-500/20 text-red-400",
  rescheduled:      "bg-purple-500/20 text-purple-400",
};

function StatusBadge({ status }) {
  return (
    <span className={`inline-flex items-center px-2.5 py-0.5 rounded-full text-xs font-medium ${STATUS_COLORS[status] || "bg-muted text-muted-foreground"}`}>
      {status.replace(/_/g, " ")}
    </span>
  );
}
```

## Chat Bubbles

Conversations page uses directional bubbles with asymmetric rounding:

```jsx
// Outbound (from shop) — gold, right-aligned
<div className="flex justify-end">
  <div className="bg-primary text-primary-foreground rounded-2xl rounded-br-sm px-4 py-2 max-w-xs">
    <p className="text-sm">{message.body}</p>
    <span className="text-xs opacity-70 mt-1 block">{formatTime(message.timestamp)}</span>
  </div>
</div>

// Inbound (from client) — secondary, left-aligned
<div className="flex justify-start">
  <div className="bg-secondary text-foreground rounded-2xl rounded-bl-sm px-4 py-2 max-w-xs">
    <p className="text-sm">{message.body}</p>
    <span className="text-xs text-muted-foreground mt-1 block">{formatTime(message.timestamp)}</span>
  </div>
</div>
```

**Key detail:** `rounded-br-sm` on outbound (bottom-right small) and `rounded-bl-sm` on inbound (bottom-left small) create the speech-bubble tail effect.

## Toasts

Use Sonner exclusively. Never use `window.alert()` or custom toast implementations.

```jsx
import { toast } from "sonner";

toast.success("Appointment confirmed");
toast.error("Failed to update status");
toast.success("Client added", { description: "SMS consent recorded" });
```

The `<Toaster />` is mounted once in `App.js` with `position="top-right"` and `richColors`.

## WARNING: Inline Styles on Components

**The Problem:**

```jsx
// BAD — hardcoded colors bypass theming
<Card style={{ backgroundColor: '#1a1a1a', borderColor: '#333' }}>
```

**Why This Breaks:**
1. Inline styles have highest specificity — impossible to override with Tailwind
2. Hex values don't update when CSS variables change
3. Creates visual inconsistency across the dashboard

**The Fix:**

```jsx
// GOOD — use design system classes
<Card className="bg-card border-border">
```

**When You Might Be Tempted:** Recharts components require inline style objects for tooltips and containers. This is the ONE exception — see the **recharts** skill for proper chart styling.

## WARNING: Custom Components Over shadcn

**The Problem:**

```jsx
// BAD — rebuilding what shadcn provides
function CustomSelect({ options, value, onChange }) {
  const [open, setOpen] = useState(false);
  return (
    <div className="relative">
      <button onClick={() => setOpen(!open)}>
        {value || "Select..."}
      </button>
      {open && <ul className="absolute">{/* options */}</ul>}
    </div>
  );
}
```

**Why This Breaks:**
1. Missing keyboard navigation, ARIA attributes, focus management
2. shadcn/ui + Radix handles accessibility out of the box
3. Custom implementations drift from the design system over time

**The Fix:**

```jsx
// GOOD — use existing shadcn components
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";

<Select value={value} onValueChange={onChange}>
  <SelectTrigger><SelectValue placeholder="Select..." /></SelectTrigger>
  <SelectContent>
    {options.map(o => <SelectItem key={o.value} value={o.value}>{o.label}</SelectItem>)}
  </SelectContent>
</Select>
```

**When You Might Be Tempted:** When the shadcn component doesn't exactly match your design. Extend it via `className` and `cn()` instead of rebuilding.
