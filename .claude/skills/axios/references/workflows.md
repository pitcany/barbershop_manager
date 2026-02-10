# Axios Workflows Reference

## Contents
- Adding a New Page with API Calls
- Adding a New API Call to an Existing Page
- Error Handling Decision Tree
- Auth Flow
- Debugging API Issues

## Adding a New Page with API Calls

Copy this checklist and track progress:
- [ ] Step 1: Create page file in `frontend/src/pages/` (PascalCase.jsx)
- [ ] Step 2: Import axios and API constant
- [ ] Step 3: Add loading/error state with `useState`
- [ ] Step 4: Fetch data in `useEffect` on mount
- [ ] Step 5: Add route in `App.js` wrapped in `<ProtectedRoute>`
- [ ] Step 6: Add sidebar link in `frontend/src/components/layout/Layout.jsx`

Standard page boilerplate:

```jsx
import { useState, useEffect } from "react";
import axios from "axios";
import { API } from "../App";
import Layout from "../components/layout/Layout";
import { toast } from "sonner";

export default function NewPage() {
  const [data, setData] = useState([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    fetchData();
  }, []);

  const fetchData = async () => {
    try {
      const response = await axios.get(`${API}/new-endpoint`);
      setData(response.data.items);
    } catch (error) {
      console.error("Failed to fetch data:", error);
      toast.error("Failed to load data");
    } finally {
      setLoading(false);
    }
  };

  return (
    <Layout title="New Page">
      {loading ? <div>Loading...</div> : <div>{/* render data */}</div>}
    </Layout>
  );
}
```

For **public pages** (no auth required), define `API` locally instead of importing from App:

```jsx
const BACKEND_URL = process.env.REACT_APP_BACKEND_URL;
const API = `${BACKEND_URL}/api`;
```

And use a plain `<Route>` without `<ProtectedRoute>` in App.js.

## Adding a New API Call to an Existing Page

1. Add the async function following the existing try/catch/finally pattern
2. Wire it to a UI trigger (useEffect, button onClick, form onSubmit)
3. If it's a mutation (POST/PATCH/DELETE), refetch the list data after success

```jsx
// Mutation pattern — always refetch
const handleDelete = async (id) => {
  try {
    await axios.delete(`${API}/items/${id}`);
    toast.success("Item deleted");
    fetchItems(); // refetch to sync UI
  } catch (error) {
    toast.error("Failed to delete item");
  }
};
```

Validation loop for mutations:
1. Make the API call
2. Check response — if error, show toast with `error.response?.data?.detail`
3. If success, refetch the parent list and show success toast
4. Only proceed when the toast confirms success

## Error Handling Decision Tree

Choose the right pattern based on context:

| Context | Pattern | Example |
|---------|---------|---------|
| List page fetch fails | Console + toast | `console.error(...)` + `toast.error("Failed to load X")` |
| Mutation fails | Toast with server detail | `toast.error(error.response?.data?.detail \|\| "Fallback")` |
| Auth check on mount | Silent + clear token | `localStorage.removeItem("token")` |
| Form submission fails | Toast + keep form state | Don't reset form on error |
| Background refresh fails | Console only | `console.error(...)` — don't interrupt user |

### WARNING: Swallowing errors silently

**The Problem:**
```jsx
// BAD — catch with no feedback
catch (error) {
  // nothing
}
```

**Why This Breaks:** Users see a spinner that never resolves, or stale data with no indication something went wrong.

**The Fix:** Always provide at least one feedback mechanism — `console.error`, `toast.error`, or clear the loading state.

### WARNING: Not handling loading states in finally

**The Problem:**
```jsx
// BAD — loading stays true if the request fails
setLoading(true);
try {
  const response = await axios.get(`${API}/data`);
  setData(response.data);
  setLoading(false); // only reached on success
} catch (error) {
  toast.error("Failed");
  // loading is still true — spinner forever
}
```

**The Fix:**
```jsx
// GOOD — finally always runs
try {
  const response = await axios.get(`${API}/data`);
  setData(response.data);
} catch (error) {
  toast.error("Failed");
} finally {
  setLoading(false);
}
```

## Auth Flow

The auth flow is split between `App.js` (interceptors + context) and `LoginPage.jsx`:

```
Login form submit
  → AuthContext.login(username, password)
    → axios.post(`${API}/auth/login`, { username, password })
    → store token in localStorage
    → axios.get(`${API}/auth/me`) to hydrate user
    → set user in context

Subsequent requests
  → request interceptor reads token from localStorage
  → attaches Authorization: Bearer <token>

401 response (expired/invalid token)
  → response interceptor catches it
  → clears localStorage
  → hard redirects to /login via window.location.href
```

The 401 interceptor uses `window.location.href` (not React Router navigate) because interceptors run outside React's component tree. This causes a full page reload, which is intentional — it clears all component state.

### WARNING: Checking auth status with API calls from interceptors

**The Problem:** Adding refresh token logic or retry logic inside the response interceptor without careful handling creates infinite loops (401 triggers refresh, refresh gets 401, triggers refresh...).

**The Fix:** If adding token refresh, use a flag to prevent recursive retries:

```jsx
let isRefreshing = false;

axios.interceptors.response.use(
  (response) => response,
  async (error) => {
    if (error.response?.status === 401 && !isRefreshing) {
      isRefreshing = true;
      try {
        // refresh logic here
      } finally {
        isRefreshing = false;
      }
    }
    return Promise.reject(error);
  }
);
```

## Debugging API Issues

When an API call fails:

1. Check the browser Network tab — is the request reaching the backend?
2. Verify `REACT_APP_BACKEND_URL` is set (check `.env` or terminal output)
3. Check if backend is running on port 8001
4. For auth errors: inspect the request headers — is `Authorization: Bearer ...` present?
5. For CORS errors: check `CORS_ORIGINS` env var on the backend

Common mistakes:
- Missing `REACT_APP_` prefix on env vars (CRA requirement)
- Backend not running or on wrong port
- Token expired — clear localStorage and re-login
- Sending wrong Content-Type — axios defaults to `application/json`, which matches the **fastapi** backend expectations

For backend endpoint details, see the **fastapi** skill.
