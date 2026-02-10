# Data Fetching Reference

## Contents
- Current Pattern: Direct Axios Calls
- Populating Forms from API Data
- Form Submission Pattern
- Server Error Handling in Forms
- WARNING: Missing Data Fetching Library

## Current Pattern: Direct Axios Calls

This project uses direct `axios` calls in components. There is no React Query, SWR, or data fetching library. See the **axios** skill for the base pattern and interceptors configured in `frontend/src/App.js`.

```jsx
const API = process.env.REACT_APP_BACKEND_URL || "http://localhost:8001/api";

// Typical fetch pattern in pages
const [data, setData] = useState(null);
const [loading, setLoading] = useState(true);

useEffect(() => {
  async function fetch() {
    try {
      const { data } = await axios.get(`${API}/shop/policy`);
      setData(data);
    } catch (error) {
      toast.error("Failed to load data");
    } finally {
      setLoading(false);
    }
  }
  fetch();
}, []);
```

## Populating Forms from API Data

When a form needs existing data (e.g., SettingsPage loading shop policy), fetch in `useEffect` and call `form.reset()`:

```jsx
const form = useForm({
  resolver: zodResolver(policySchema),
  defaultValues: {
    deposit_amount: 0,
    confirmation_window_hours: 24,
    cancellation_window_hours: 4,
    max_messages_per_day: 4,
  },
});

useEffect(() => {
  async function loadPolicy() {
    try {
      const { data } = await axios.get(`${API}/shop/policy`);
      form.reset(data);
    } catch (error) {
      toast.error("Failed to load settings");
    }
  }
  loadPolicy();
}, [form]);
```

### WARNING: Using `defaultValues` for Async Data

**The Problem:**

```jsx
// BAD - defaultValues only runs once at mount
const form = useForm({
  defaultValues: async () => {
    const { data } = await axios.get(`${API}/shop/policy`);
    return data;
  },
});
```

**Why This Breaks:**
1. RHF v7 supports async `defaultValues` but provides no loading state
2. No error handling — a network failure silently leaves the form empty
3. No way to refetch after the initial mount

**The Fix:**

```jsx
// GOOD - explicit fetch with error handling and loading state
const [loading, setLoading] = useState(true);

useEffect(() => {
  axios.get(`${API}/shop/policy`)
    .then(({ data }) => form.reset(data))
    .catch(() => toast.error("Failed to load settings"))
    .finally(() => setLoading(false));
}, [form]);

if (loading) return <Skeleton className="h-64" />;
```

## Form Submission Pattern

RHF's `handleSubmit` only calls your function when validation passes. Use `isSubmitting` instead of a manual loading state:

```jsx
const onSubmit = async (data) => {
  try {
    await axios.patch(`${API}/shop/policy`, data);
    toast.success("Settings saved");
  } catch (error) {
    toast.error(error.response?.data?.detail || "Failed to save");
  }
};

<form onSubmit={form.handleSubmit(onSubmit)}>
  {/* fields */}
  <Button type="submit" disabled={form.formState.isSubmitting}>
    {form.formState.isSubmitting ? "Saving..." : "Save"}
  </Button>
</form>
```

`isSubmitting` is `true` from the moment `handleSubmit` calls your async function until it resolves or rejects. No manual `setLoading(true/false)` needed.

## Server Error Handling in Forms

### Field-Level Server Errors

When the backend returns validation errors for specific fields, use `form.setError()`:

```jsx
const onSubmit = async (data) => {
  try {
    await axios.post(`${API}/public/sms-consent`, data);
    toast.success("Consent recorded");
  } catch (error) {
    const detail = error.response?.data?.detail;
    if (typeof detail === "string" && detail.includes("phone")) {
      form.setError("phone", { message: detail });
    } else if (Array.isArray(detail)) {
      // FastAPI validation errors come as array
      detail.forEach((err) => {
        const field = err.loc?.[err.loc.length - 1];
        if (field) form.setError(field, { message: err.msg });
      });
    } else {
      toast.error(detail || "Submission failed");
    }
  }
};
```

### Root-Level Server Errors

For errors not tied to a specific field, use `form.setError("root", ...)`:

```jsx
try {
  await login(data.username, data.password);
} catch (error) {
  if (error.response?.status === 401) {
    form.setError("root", { message: "Invalid username or password" });
  }
}

// Display root errors in the form
{form.formState.errors.root && (
  <p className="text-sm text-destructive">{form.formState.errors.root.message}</p>
)}
```

## WARNING: Missing Data Fetching Library

This project fetches data with raw `useEffect` + `axios`. This means:
- No request deduplication — two components mounting simultaneously fetch twice
- No caching — navigating away and back refetches everything
- No background refetching — stale data shown until manual refresh
- No optimistic updates — UI waits for server round-trip

For form-heavy pages this is acceptable since form data is edit-specific. But for list pages (appointments, conversations, waitlist), consider adding **TanStack Query** (React Query) for:
- Automatic cache invalidation after form mutations
- Background refetching for live dashboard data
- Loading/error states without boilerplate `useState`

See the **react** skill for component lifecycle patterns.
See the **fastapi** skill for the API endpoints these forms submit to.
