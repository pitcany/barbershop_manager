# Components Reference

## Contents
- Component Architecture
- Page Component Pattern
- Layout Component
- shadcn/ui Usage
- Compound Component Patterns
- WARNING: Component Anti-Patterns

## Component Architecture

```
src/
├── pages/           # 7 page components (PascalCase.jsx)
├── components/
│   ├── ui/          # 46 shadcn/ui primitives (kebab-case.jsx)
│   └── layout/      # Layout.jsx — sidebar + page wrapper
├── hooks/           # use-toast.js (legacy, unused)
└── lib/             # utils.js (cn() helper)
```

**Naming rules:**
- Pages: `PascalCase.jsx` — `DashboardPage.jsx`, `SettingsPage.jsx`
- UI components: `kebab-case.jsx` — `button.jsx`, `dropdown-menu.jsx`
- Each page is a `default export function`

## Page Component Pattern

Every page follows this exact structure:

```jsx
import { useState, useEffect } from "react";
import axios from "axios";
import { API } from "../App";
import Layout from "../components/layout/Layout";
// shadcn/ui imports
// lucide-react icons
// date-fns if needed
// sonner toast

export default function PageName() {
  const [data, setData] = useState(/* initial */);
  const [loading, setLoading] = useState(true);

  useEffect(() => { fetchData(); }, []);

  const fetchData = async () => { /* axios call */ };

  if (loading) return <Layout title="Title"><Skeleton /></Layout>;

  return (
    <Layout title="Title">
      <div data-testid="page-name" className="space-y-6">
        {/* content */}
      </div>
    </Layout>
  );
}
```

## Layout Component

`Layout.jsx` wraps all authenticated pages. Provides sidebar nav, mobile hamburger menu, and page title.

```jsx
// Usage in any page
import Layout from "../components/layout/Layout";

return (
  <Layout title="Dashboard">
    {children}
  </Layout>
);
```

**Layout props:**
- `title` (optional string) — rendered as `<h1>` above content
- `children` — page content

**Navigation items** are defined as a static array (Layout.jsx:17-23):

```jsx
const navItems = [
  { path: "/", label: "Dashboard", icon: LayoutDashboard },
  { path: "/conversations", label: "Conversations", icon: MessageSquare },
  { path: "/appointments", label: "Appointments", icon: Calendar },
  { path: "/waitlist", label: "Waitlist", icon: Users },
  { path: "/settings", label: "Settings", icon: Settings },
];
```

## shadcn/ui Usage

See the **shadcn-ui** skill for full component API. Key patterns in this codebase:

### Import Pattern

```jsx
// Pages use relative imports
import { Card, CardContent, CardHeader, CardTitle } from "../components/ui/card";
import { Button } from "../components/ui/button";

// UI components use @/ alias
import { cn } from "@/lib/utils";
```

### cn() Utility

```jsx
// src/lib/utils.js — clsx + tailwind-merge
import { clsx } from "clsx";
import { twMerge } from "tailwind-merge";
export function cn(...inputs) { return twMerge(clsx(inputs)); }
```

Use `cn()` when merging conditional Tailwind classes to avoid conflicts.

### Confirmation Dialog Pattern (WaitlistPage.jsx:181-210)

```jsx
<AlertDialog>
  <AlertDialogTrigger asChild>
    <Button variant="ghost" size="icon">
      <Trash2 className="w-4 h-4" />
    </Button>
  </AlertDialogTrigger>
  <AlertDialogContent>
    <AlertDialogHeader>
      <AlertDialogTitle>Remove from Waitlist?</AlertDialogTitle>
      <AlertDialogDescription>
        This will remove {entry.client?.name} from the waitlist.
      </AlertDialogDescription>
    </AlertDialogHeader>
    <AlertDialogFooter>
      <AlertDialogCancel>Cancel</AlertDialogCancel>
      <AlertDialogAction
        onClick={() => removeFromWaitlist(entry.id)}
        className="bg-destructive text-destructive-foreground"
      >
        Remove
      </AlertDialogAction>
    </AlertDialogFooter>
  </AlertDialogContent>
</AlertDialog>
```

### Icon Usage Pattern

Icons from `lucide-react` are used inline, sized with Tailwind:

```jsx
import { Calendar, DollarSign, Users } from "lucide-react";

<Calendar className="w-4 h-4 text-muted-foreground" />
<DollarSign className="w-5 h-5 text-primary" />
```

## Compound Component Patterns

Card is the most-used compound component:

```jsx
<Card className="bg-card border-border">
  <CardHeader>
    <CardTitle className="font-heading">{title}</CardTitle>
    <CardDescription>{description}</CardDescription>
  </CardHeader>
  <CardContent className="p-6">
    {/* content */}
  </CardContent>
</Card>
```

## WARNING: Component Anti-Patterns

### WARNING: Index as Key in Static Lists

**The Problem:**

```jsx
// BAD — Using index for dynamic lists where items can be reordered/removed
{items.map((item, index) => <Component key={index} />)}
```

**Why This Breaks:** React reconciliation uses keys to track identity. Index keys cause state to bleed between items on reorder/delete.

**The Fix:** Use stable unique IDs. This codebase uses `entry.id` or `apt.id` for dynamic lists:

```jsx
// GOOD — WaitlistPage.jsx uses entity IDs
{waitlist.map((entry) => (
  <TableRow key={entry.id}>{/* ... */}</TableRow>
))}
```

**When index is acceptable:** Static lists that never change (skeleton placeholders, stat cards). The codebase correctly uses index only for these: `{[...Array(4)].map((_, i) => ...)}`.

### WARNING: Prop Drilling

This codebase avoids prop drilling by using Context for auth and keeping all other state local to each page. If you add shared state beyond auth, use Context — not prop chains through Layout.