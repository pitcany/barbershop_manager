---
name: react
description: |
  Manages React 19 components, hooks, Context API auth, and state patterns for the Barbershop Autopilot SPA.
  Use when: creating/modifying React components, adding pages, working with auth context, data fetching, state management, or routing in the frontend.
allowed-tools: Read, Edit, Write, Glob, Grep, Bash, mcp__plugin_context7-plugin_context7__resolve-library-id, mcp__plugin_context7-plugin_context7__query-docs, mcp__web-search-prime__webSearchPrime, mcp__plugin_playwright_playwright__browser_navigate, mcp__plugin_playwright_playwright__browser_take_screenshot, mcp__plugin_playwright_playwright__browser_snapshot, mcp__plugin_playwright_playwright__browser_click
---

# React Skill

React 19 SPA using CRA (via CRACO), Context API for auth, direct axios calls for data fetching, shadcn/ui components, and Tailwind CSS. JavaScript only (no TypeScript). All pages follow a consistent pattern: `useState` + `useEffect` on mount + axios + loading skeletons + toast feedback.

## Quick Start

### Page Component Structure

```jsx
// frontend/src/pages/ExamplePage.jsx
import { useState, useEffect } from "react";
import axios from "axios";
import { API } from "../App";
import Layout from "../components/layout/Layout";
import { Card, CardContent } from "../components/ui/card";
import { toast } from "sonner";

export default function ExamplePage() {
  const [data, setData] = useState([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => { fetchData(); }, []);

  const fetchData = async () => {
    try {
      const response = await axios.get(`${API}/endpoint`);
      setData(response.data.items);
    } catch (error) {
      console.error("Failed to fetch:", error);
      toast.error("Failed to load data");
    } finally {
      setLoading(false);
    }
  };

  if (loading) {
    return (
      <Layout title="Example">
        <Card className="bg-card border-border animate-pulse">
          <CardContent className="p-6"><div className="h-20 bg-muted rounded" /></CardContent>
        </Card>
      </Layout>
    );
  }

  return <Layout title="Example">{/* content */}</Layout>;
}
```

### Auth Context Usage

```jsx
import { useAuth } from "../App";

function MyComponent() {
  const { user, isAuthenticated, login, logout } = useAuth();
  // user: { username, ... } | null
  // isAuthenticated: boolean (derived as !!user)
}
```

## Key Concepts

| Concept | Pattern | Location |
|---------|---------|----------|
| Auth | Context + localStorage JWT | `App.js:17-113` |
| API base | `export const API = \`${BACKEND_URL}/api\`` | `App.js:22` |
| Protected routes | `<ProtectedRoute>` wrapper | `App.js:44-62` |
| Imports | `@/` alias maps to `src/` | `craco.config.js`, `jsconfig.json` |
| Toast | `sonner` (not shadcn toast) | `import { toast } from "sonner"` |
| Icons | `lucide-react` | All pages |
| Dates | `date-fns` format | All pages |

## Common Patterns

### Skeleton Loading

**When:** Any page that fetches data on mount.

```jsx
{loading ? (
  [...Array(4)].map((_, i) => (
    <Card key={i} className="bg-card border-border animate-pulse">
      <CardContent className="p-6">
        <div className="h-20 bg-muted rounded" />
      </CardContent>
    </Card>
  ))
) : /* render data */}
```

### Inline Status Update

**When:** Changing entity status without a modal.

```jsx
const updateStatus = async (id, newStatus) => {
  try {
    await axios.patch(`${API}/appointments/${id}/status?status=${newStatus}`);
    toast.success("Status updated");
    fetchAppointments(); // refetch
  } catch (error) {
    toast.error("Failed to update status");
  }
};
```

## See Also

- [hooks](references/hooks.md)
- [components](references/components.md)
- [data-fetching](references/data-fetching.md)
- [state](references/state.md)
- [forms](references/forms.md)
- [performance](references/performance.md)

## Related Skills

- See the **shadcn-ui** skill for component primitives and CVA patterns
- See the **tailwind** skill for styling conventions and CSS variables
- See the **axios** skill for HTTP client patterns and interceptors
- See the **recharts** skill for dashboard chart patterns
- See the **react-hook-form** skill for form validation with Zod
- See the **jwt** skill for authentication token flow
- See the **frontend-design** skill for design system and dark theme

## Documentation Resources

> Fetch latest React documentation with Context7.

**How to use Context7:**
1. Use `mcp__plugin_context7-plugin_context7__resolve-library-id` to search for "react"
2. **Prefer website documentation** (IDs starting with `/websites/`) over source code repositories
3. Query with `mcp__plugin_context7-plugin_context7__query-docs` using the resolved library ID

**Recommended Queries:**
- "React hooks useState useEffect useCallback useMemo"
- "React Context API patterns"
- "React 19 new features"