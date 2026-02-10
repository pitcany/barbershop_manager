# Axios Patterns Reference

## Contents
- Import and Base URL
- GET Requests
- POST and PATCH Requests
- DELETE Requests
- Query Parameters
- Parallel Requests
- Error Handling
- Anti-Patterns

## Import and Base URL

Protected pages import from App.js:

```jsx
import axios from "axios";
import { API } from "../App";
// API = "http://localhost:8001/api" (from REACT_APP_BACKEND_URL)
```

Public pages (no auth needed) define `API` locally to avoid importing auth interceptors unnecessarily:

```jsx
// frontend/src/pages/SMSConsentPage.jsx
const BACKEND_URL = process.env.REACT_APP_BACKEND_URL;
const API = `${BACKEND_URL}/api`;
```

Both approaches work because interceptors are registered globally — the local definition is a stylistic choice that keeps the public page self-contained.

## GET Requests

Standard pattern used across all pages:

```jsx
// GOOD — consistent try/catch/finally with loading state
const fetchAppointments = async () => {
  setLoading(true);
  try {
    const response = await axios.get(`${API}/appointments?${params}`);
    setAppointments(response.data.appointments);
    setTotal(response.data.total);
  } catch (error) {
    console.error("Failed to fetch appointments:", error);
    toast.error("Failed to load appointments");
  } finally {
    setLoading(false);
  }
};
```

## POST and PATCH Requests

POST for creation, PATCH for updates — matches the **fastapi** backend conventions:

```jsx
// POST — creating new resources
await axios.post(`${API}/public/sms-consent`, formData);

// POST — triggering actions
await axios.post(`${API}/sms/send-test`, {
  to_phone: testSMS.phone,
  message: testSMS.message
});

// PATCH — updating resources (status via query param, body for objects)
await axios.patch(`${API}/appointments/${appointmentId}/status?status=${newStatus}`);
await axios.patch(`${API}/shop/policy`, formData);
```

## DELETE Requests

```jsx
await axios.delete(`${API}/waitlist/${entryId}`);
toast.success("Removed from waitlist");
fetchWaitlist(); // refetch after mutation
```

## Query Parameters

This project builds query strings manually with `URLSearchParams`:

```jsx
// GOOD — URLSearchParams for dynamic filters
const params = new URLSearchParams();
if (statusFilter !== "all") params.append("status", statusFilter);
if (dateFilter) params.append("date", format(dateFilter, "yyyy-MM-dd"));
params.append("limit", limit);
params.append("skip", page * limit);

const response = await axios.get(`${API}/appointments?${params}`);
```

```jsx
// BAD — string interpolation for multiple params
const response = await axios.get(
  `${API}/appointments?status=${status}&limit=${limit}&skip=${skip}`
);
// Breaks when values contain special characters, harder to conditionally add params
```

## Parallel Requests

Use `Promise.all` when fetching independent data for the same view:

```jsx
// GOOD — parallel fetches for dashboard
const [statsRes, chartRes] = await Promise.all([
  axios.get(`${API}/dashboard/stats`),
  axios.get(`${API}/dashboard/revenue-chart?days=14`)
]);
```

```jsx
// BAD — sequential when requests are independent
const statsRes = await axios.get(`${API}/dashboard/stats`);
const chartRes = await axios.get(`${API}/dashboard/revenue-chart?days=14`);
// Doubles the wait time for no reason
```

## Error Handling

Three error handling patterns used in this codebase:

**1. User-facing toast with server detail:**
```jsx
catch (error) {
  toast.error(error.response?.data?.detail || "Failed to send test SMS");
}
```

**2. Console + toast (most common for list pages):**
```jsx
catch (error) {
  console.error("Failed to fetch appointments:", error);
  toast.error("Failed to load appointments");
}
```

**3. Silent failure (auth check on mount):**
```jsx
catch (error) {
  localStorage.removeItem("token");
  // No toast — user just isn't logged in
}
```

Always use `error.response?.data?.detail` — the FastAPI backend returns `{"detail": "..."}` for all error responses.

## Anti-Patterns

### WARNING: Creating axios instances

**The Problem:**
```jsx
// BAD — creating a custom instance bypasses the global interceptors
const api = axios.create({ baseURL: API });
const response = await api.get("/appointments");
// Auth header is NOT attached, 401 redirect does NOT work
```

**Why This Breaks:** The JWT interceptor and 401 redirect are registered on the global axios instance in `App.js`. A custom instance has none of that.

**The Fix:** Always use `import axios from "axios"` directly.

### WARNING: Manual Authorization headers

**The Problem:**
```jsx
// BAD — duplicating what the interceptor already does
await axios.get(`${API}/appointments`, {
  headers: { Authorization: `Bearer ${localStorage.getItem("token")}` }
});
```

**Why This Breaks:** The request interceptor already attaches the token. Manual headers create two sources of truth and will break if auth strategy changes.

**The Fix:** Just call `axios.get(url)` — the interceptor handles auth.

### WARNING: Using axios.defaults.baseURL

**The Problem:**
```jsx
// BAD — mutating global defaults
axios.defaults.baseURL = API;
await axios.get("/appointments");
```

**Why This Breaks:** This project uses template literals with the `API` constant for explicitness. Mixing approaches makes URL construction unpredictable and breaks public pages that define their own `API`.

**The Fix:** Always use `` `${API}/endpoint` `` template literals.

### WARNING: Forgetting to refetch after mutations

**The Problem:**
```jsx
// BAD — UI shows stale data after mutation
await axios.patch(`${API}/appointments/${id}/status?status=confirmed`);
toast.success("Status updated");
// Missing: fetchAppointments() call
```

**Why This Breaks:** This project has no client-side cache or state management. The only way to get fresh data is to refetch.

**The Fix:**
```jsx
await axios.patch(`${API}/appointments/${id}/status?status=confirmed`);
toast.success("Status updated");
fetchAppointments(); // always refetch after mutation
```
