# State Management Reference

## Contents
- State Architecture
- Auth Context (Global State)
- Local Component State
- URL State via React Router
- Derived State
- WARNING: State Anti-Patterns

## State Architecture

This codebase uses **three layers** of state — no Redux, no Zustand, no external state libraries.

| Layer | Tool | Scope | Example |
|-------|------|-------|---------|
| Global | React Context | App-wide auth | `AuthContext` in App.js |
| Local | `useState` | Single component | Page data, loading, filters |
| URL | React Router | Navigation state | `useParams()`, `useLocation()` |

## Auth Context (Global State)

Defined in App.js:17-113. The only Context in the codebase.

```jsx
// Creating context
const AuthContext = createContext(null);
export const useAuth = () => useContext(AuthContext);

// Provider value shape
<AuthContext.Provider value={{
  user,              // { username, ... } | null
  isAuthenticated,   // boolean (!!user)
  loading,           // boolean — true during initial auth check
  login,             // async (username, password) => response
  logout,            // () => void — clears token + user
}}>
```

**Auth flow:**
1. App mounts → `checkAuth()` reads JWT from `localStorage`
2. If token exists → validates via `GET /api/auth/me`
3. If valid → sets `user`, if invalid → clears token
4. `login()` → `POST /api/auth/login` → stores token → calls `checkAuth()`
5. `logout()` → removes token → sets `user` to `null`

## Local Component State

Every page manages its own data. Common state variables:

```jsx
// Data + loading (every page)
const [data, setData] = useState([]);
const [loading, setLoading] = useState(true);

// Filters (AppointmentsPage)
const [statusFilter, setStatusFilter] = useState("all");
const [dateFilter, setDateFilter] = useState(null);
const [page, setPage] = useState(0);
const [total, setTotal] = useState(0);

// Form data (SettingsPage)
const [formData, setFormData] = useState({
  deposit_amount: 20,
  deposit_required_hours: 48,
  confirmation_window_hours: 24,
  cancellation_window_hours: 4,
  max_messages_per_day: 4
});

// Action states (saving, sending)
const [saving, setSaving] = useState(false);
const [sendingTest, setSendingTest] = useState(false);
```

## URL State via React Router

### Route Params (ConversationsPage.jsx:22)

```jsx
const { clientId } = useParams();
// Used to select conversation from URL: /conversations/:clientId
```

### Location State for Redirect (LoginPage.jsx:19)

```jsx
const from = location.state?.from?.pathname || "/";
// ProtectedRoute passes current location when redirecting to /login
// After login, user returns to where they were
```

### Programmatic Navigation (ConversationsPage.jsx:23)

```jsx
const navigate = useNavigate();
const handleSelectConversation = (cId) => {
  navigate(`/conversations/${cId}`);
};
```

## Derived State

Computed during render — no extra `useState` needed:

```jsx
// ConversationsPage.jsx:74-77 — Filter conversations client-side
const filteredConversations = conversations.filter(conv =>
  conv.client?.name?.toLowerCase().includes(searchTerm.toLowerCase()) ||
  conv.client?.phone?.includes(searchTerm)
);

// AppointmentsPage.jsx:112 — Compute pagination
const totalPages = Math.ceil(total / limit);

// App.js:105 — Derived auth boolean
isAuthenticated: !!user
```

## Functional State Updates

When the new state depends on previous state, use the functional form:

```jsx
// SettingsPage.jsx:178 — Spread previous + update one field
onChange={(e) => setFormData(prev => ({
  ...prev,
  deposit_amount: parseFloat(e.target.value)
}))}

// AppointmentsPage.jsx:292 — Constrained pagination
onClick={() => setPage(p => Math.max(0, p - 1))}
onClick={() => setPage(p => Math.min(totalPages - 1, p + 1))}
```

## WARNING: State Anti-Patterns

### WARNING: Storing Derived Values in State

**The Problem:**

```jsx
// BAD — Extra state for something computable
const [filteredItems, setFilteredItems] = useState([]);
useEffect(() => {
  setFilteredItems(items.filter(i => i.active));
}, [items]);
```

**Why This Breaks:**
1. Extra render cycle on every change
2. Possible sync bugs if you forget to update the effect deps
3. More code for zero benefit

**The Fix:** Compute inline during render.

```jsx
// GOOD
const filteredItems = items.filter(i => i.active);
```

### WARNING: Multiple setState Calls That Should Be One Object

**The Problem:**

```jsx
// BAD — Two renders instead of one
setLoading(false);
setError("Something failed");
```

**Why This Breaks:** In React 18+, these batch automatically inside event handlers and effects. But in async callbacks outside React's control, they may cause separate renders.

**The Fix:** Group related state into one object, or use React 18+'s automatic batching (which this codebase already benefits from).

### WARNING: Prop Drilling Beyond Layout

If you need to share state between sibling pages, use Context. Do NOT pass state through Layout props — Layout is a presentation wrapper, not a state container.