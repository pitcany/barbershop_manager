# Hooks Reference

## Contents
- Custom Hooks in This Codebase
- useEffect Patterns
- useRef Patterns
- WARNING: Common Hook Anti-Patterns

## Custom Hooks in This Codebase

This project has exactly ONE custom hook. All other state management uses inline `useState`/`useEffect`.

### useAuth (App.js:19)

```jsx
export const useAuth = () => useContext(AuthContext);

// Returns: { user, isAuthenticated, loading, login, logout }
// Used in: Layout.jsx, LoginPage.jsx, ProtectedRoute
```

### use-toast.js (Legacy)

The `use-toast.js` hook exists in `src/hooks/` but the codebase uses `sonner` directly via `import { toast } from "sonner"`. The `use-toast` hook is the shadcn default but is **not actively used** in any page component.

**When adding toast notifications:** Use `sonner` directly, not `useToast()`.

```jsx
// GOOD - What this codebase uses
import { toast } from "sonner";
toast.success("Saved");
toast.error("Failed to load");

// AVOID - Legacy shadcn pattern (exists but unused)
import { useToast } from "@/hooks/use-toast";
const { toast } = useToast();
```

## useEffect Patterns

### Fetch on Mount

Every page uses this pattern. The dependency array is `[]` for mount-only, or includes filter state.

```jsx
// DashboardPage.jsx — mount only
useEffect(() => { fetchData(); }, []);

// AppointmentsPage.jsx — refetch on filter change
useEffect(() => {
  fetchAppointments();
}, [statusFilter, dateFilter, page]);
```

### Multiple Independent Effects

ConversationsPage uses separate effects for different concerns:

```jsx
// Fetch conversation list on mount
useEffect(() => { fetchConversations(); }, []);

// Fetch messages when clientId changes (URL param)
useEffect(() => {
  if (clientId) fetchMessages(clientId);
}, [clientId]);

// Auto-scroll when messages change
useEffect(() => { scrollToBottom(); }, [messages]);
```

### WARNING: Missing Cleanup

No page component in this codebase uses effect cleanup. This is acceptable for the current simple mount-fetch pattern but becomes a problem if:
- Polling/intervals are added
- WebSocket connections are introduced
- Components unmount before fetch completes

**The Fix (when needed):**

```jsx
useEffect(() => {
  let cancelled = false;
  const fetchData = async () => {
    const res = await axios.get(`${API}/endpoint`);
    if (!cancelled) setData(res.data);
  };
  fetchData();
  return () => { cancelled = true; };
}, []);
```

## useRef Patterns

### Scroll-to-Bottom (ConversationsPage.jsx:29)

```jsx
const messagesEndRef = useRef(null);

const scrollToBottom = () => {
  messagesEndRef.current?.scrollIntoView({ behavior: "smooth" });
};

// In JSX — empty div at end of message list
<div ref={messagesEndRef} />
```

## WARNING: Common Hook Anti-Patterns

### WARNING: useEffect for Derived State

**The Problem:**

```jsx
// BAD — Syncing state that can be computed
const [filteredItems, setFilteredItems] = useState([]);
useEffect(() => {
  setFilteredItems(items.filter(i => i.status === filter));
}, [items, filter]);
```

**Why This Breaks:**
1. Extra render cycle — state update triggers re-render
2. Stale frame — UI shows old filtered list for one frame
3. Unnecessary complexity for a pure computation

**The Fix:**

```jsx
// GOOD — Compute during render (this codebase does this correctly)
const filteredConversations = conversations.filter(conv =>
  conv.client?.name?.toLowerCase().includes(searchTerm.toLowerCase())
);
```

**This codebase gets this right** in ConversationsPage.jsx:74-77.

### WARNING: Missing Dependency Array Items

**The Problem:**

```jsx
// BAD — fetchAppointments uses statusFilter but it's not in deps
useEffect(() => { fetchAppointments(); }, []);
```

**Why This Breaks:** Stale closure — `fetchAppointments` captures the initial `statusFilter` value and never updates.

**The Fix:** Include all external values used inside the effect.

```jsx
// GOOD — AppointmentsPage.jsx:70-72
useEffect(() => {
  fetchAppointments();
}, [statusFilter, dateFilter, page]);
```

### WARNING: Calling navigate() During Render

LoginPage.jsx:22-24 calls `navigate()` during render:

```jsx
if (isAuthenticated) {
  navigate(from, { replace: true });
  return null;
}
```

This works but is fragile. Prefer `<Navigate>` component (as used in ProtectedRoute) or wrap in `useEffect`.