# Data Fetching Reference

## Contents
- Fetching Pattern
- Parallel Fetches
- Filtered Fetches with Pagination
- Error Handling
- WARNING: No Caching Layer
- WARNING: useEffect for Data Fetching

## Fetching Pattern

This codebase uses **direct axios calls in useEffect**. There is no React Query, SWR, or service layer.

```jsx
// Standard pattern used in every page
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
```

**Key conventions:**
- `API` is imported from `../App` (resolves to `${REACT_APP_BACKEND_URL}/api`)
- Axios interceptor automatically adds JWT `Authorization` header (App.js:25-31)
- 401 responses auto-redirect to `/login` (App.js:33-42)

## Parallel Fetches

DashboardPage uses `Promise.all` to fetch multiple endpoints simultaneously:

```jsx
// DashboardPage.jsx:37-50
const fetchData = async () => {
  try {
    const [statsRes, chartRes] = await Promise.all([
      axios.get(`${API}/dashboard/stats`),
      axios.get(`${API}/dashboard/revenue-chart?days=14`)
    ]);
    setStats(statsRes.data);
    setChartData(chartRes.data.data);
  } catch (error) {
    console.error("Failed to fetch dashboard data:", error);
  } finally {
    setLoading(false);
  }
};
```

**When to use:** Multiple independent API calls needed on the same page. NEVER chain sequential `await` calls when the requests don't depend on each other.

## Filtered Fetches with Pagination

AppointmentsPage builds query params from filter state and refetches on any filter change:

```jsx
// AppointmentsPage.jsx:70-92
useEffect(() => { fetchAppointments(); }, [statusFilter, dateFilter, page]);

const fetchAppointments = async () => {
  setLoading(true);
  try {
    const params = new URLSearchParams();
    if (statusFilter !== "all") params.append("status", statusFilter);
    if (dateFilter) params.append("date", format(dateFilter, "yyyy-MM-dd"));
    params.append("limit", limit);
    params.append("skip", page * limit);

    const response = await axios.get(`${API}/appointments?${params}`);
    setAppointments(response.data.appointments);
    setTotal(response.data.total);
  } catch (error) {
    toast.error("Failed to load appointments");
  } finally {
    setLoading(false);
  }
};
```

**Pattern:** Filter state in dependency array → automatic refetch. Note `setLoading(true)` at the start (unlike mount-only fetches which start `true`).

## Client-Side Filtering

For small datasets, filter in the component without re-fetching:

```jsx
// ConversationsPage.jsx:74-77
const filteredConversations = conversations.filter(conv =>
  conv.client?.name?.toLowerCase().includes(searchTerm.toLowerCase()) ||
  conv.client?.phone?.includes(searchTerm)
);
```

Use client-side filtering when the full dataset is already loaded and small enough.

## Error Handling

Two patterns coexist:

```jsx
// Pattern 1: Console + toast (most pages)
catch (error) {
  console.error("Failed to fetch:", error);
  toast.error("Failed to load data");
}

// Pattern 2: Extract API error detail (LoginPage, SettingsPage)
catch (error) {
  toast.error(error.response?.data?.detail || "Login failed");
}
```

Use Pattern 2 when the backend returns meaningful error messages in `detail`.

## Mutation Pattern

All mutations follow: call API → toast → refetch:

```jsx
// WaitlistPage.jsx:59-67
const removeFromWaitlist = async (entryId) => {
  try {
    await axios.delete(`${API}/waitlist/${entryId}`);
    toast.success("Removed from waitlist");
    fetchWaitlist(); // refetch list
  } catch (error) {
    toast.error("Failed to remove from waitlist");
  }
};
```

**Key pattern:** After any mutation, call the fetch function again to refresh data. There is no optimistic update.

## WARNING: No Caching Layer

**The Problem:** Every page mount triggers a fresh API call. Navigating between pages re-fetches all data. There is no cache, deduplication, or stale-while-revalidate.

**Real-world consequence:** Navigating Dashboard → Appointments → Dashboard makes 3 API calls (2 for dashboard stats). On slow connections, the user sees loading skeletons every time.

**When this matters:** If you add frequently-visited pages or slow endpoints. For the current MVP with 7 pages and fast local API, this is acceptable.

**If you need caching:** Consider React Query (`@tanstack/react-query`). It drops into the existing pattern with minimal changes:

```jsx
// Hypothetical upgrade path
import { useQuery } from "@tanstack/react-query";

const { data: stats, isLoading } = useQuery({
  queryKey: ["dashboard-stats"],
  queryFn: () => axios.get(`${API}/dashboard/stats`).then(r => r.data),
});
```

## WARNING: useEffect for Data Fetching

**The Problem:** Raw `useEffect` + `axios` has no race condition protection, no request deduplication, and no automatic refetch on window focus.

**Why This Breaks:**
1. Fast navigation can cause state updates on unmounted components
2. No automatic retry on network failure
3. No background refetching for stale data

**When You Might Be Tempted:** This is the default pattern in the codebase and works for the MVP. Only upgrade if adding: polling, real-time updates, offline support, or complex cache invalidation.