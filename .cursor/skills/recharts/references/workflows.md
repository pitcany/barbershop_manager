# Recharts Workflows Reference

## Contents
- Adding a New Chart
- Adding a Data Series to Existing Chart
- Changing Chart Type
- Custom Legend Pattern
- Connecting to Backend Data
- Debugging Common Issues

## Adding a New Chart

Copy this checklist and track progress:
- [ ] Step 1: Define backend endpoint returning `{ data: [...] }` (see the **fastapi** skill)
- [ ] Step 2: Add state and fetch call in the page component (see the **react** skill)
- [ ] Step 3: Add chart JSX inside a Card with fixed-height container
- [ ] Step 4: Define gradient `<defs>` with unique IDs
- [ ] Step 5: Style all axes, grid, and tooltip for dark theme
- [ ] Step 6: Test with empty data, single point, and full dataset

### Template: New AreaChart in a Card

```jsx
import { AreaChart, Area, XAxis, YAxis, CartesianGrid, Tooltip, ResponsiveContainer } from "recharts";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";

function AppointmentsChart({ data }) {
  return (
    <Card>
      <CardHeader>
        <CardTitle>Appointments (30 Days)</CardTitle>
      </CardHeader>
      <CardContent>
        <div className="h-72">
          <ResponsiveContainer width="100%" height="100%">
            <AreaChart data={data} margin={{ top: 10, right: 30, left: 0, bottom: 0 }}>
              <defs>
                <linearGradient id="apptColorCompleted" x1="0" y1="0" x2="0" y2="1">
                  <stop offset="5%" stopColor="#D4AF37" stopOpacity={0.3} />
                  <stop offset="95%" stopColor="#D4AF37" stopOpacity={0} />
                </linearGradient>
              </defs>
              <CartesianGrid strokeDasharray="3 3" stroke="#27272a" />
              <XAxis dataKey="date" stroke="#a1a1aa"
                tick={{ fill: '#a1a1aa', fontSize: 12 }}
                tickFormatter={(v) => `${new Date(v).getMonth()+1}/${new Date(v).getDate()}`} />
              <YAxis stroke="#a1a1aa" tick={{ fill: '#a1a1aa', fontSize: 12 }} />
              <Tooltip contentStyle={{
                backgroundColor: '#18181b', border: '1px solid #27272a',
                borderRadius: '8px', color: '#fafafa'
              }} labelFormatter={(l) => new Date(l).toLocaleDateString()} />
              <Area type="monotone" dataKey="completed" stroke="#D4AF37"
                fillOpacity={1} fill="url(#apptColorCompleted)" name="Completed" />
            </AreaChart>
          </ResponsiveContainer>
        </div>
      </CardContent>
    </Card>
  );
}
```

## Adding a Data Series to Existing Chart

To add a third area (e.g., "pending") to the revenue chart in `frontend/src/pages/DashboardPage.jsx`:

1. **Add gradient in `<defs>`:**
```jsx
<linearGradient id="colorPending" x1="0" y1="0" x2="0" y2="1">
  <stop offset="5%" stopColor="#D4AF37" stopOpacity={0.3} />
  <stop offset="95%" stopColor="#D4AF37" stopOpacity={0} />
</linearGradient>
```

2. **Add `<Area>` component after existing areas:**
```jsx
<Area type="monotone" dataKey="pending" stroke="#D4AF37"
  fillOpacity={1} fill="url(#colorPending)" name="Pending" />
```

3. **Update backend** to include `pending` in the aggregation pipeline output.

4. **Update legend** — the project uses a custom HTML legend, not Recharts `<Legend>`:
```jsx
<div className="flex items-center gap-4 mt-4 justify-center text-sm">
  <span className="flex items-center gap-1.5">
    <span className="w-3 h-3 rounded-full" style={{ backgroundColor: '#D4AF37' }} />
    <span className="text-muted-foreground">Pending</span>
  </span>
</div>
```

## Changing Chart Type

Replace `AreaChart`/`Area` with `BarChart`/`Bar` or `LineChart`/`Line`. The container, axes, grid, and tooltip stay identical.

```jsx
// AreaChart → BarChart
import { BarChart, Bar } from "recharts";

<BarChart data={data} margin={{ top: 10, right: 30, left: 0, bottom: 0 }}>
  {/* CartesianGrid, XAxis, YAxis, Tooltip — unchanged */}
  <Bar dataKey="recovered" fill="#10b981" radius={[4, 4, 0, 0]} />
  <Bar dataKey="lost" fill="#ef4444" radius={[4, 4, 0, 0]} />
</BarChart>
```

**Note:** For BarChart, use `fill` directly instead of gradient `<defs>`. `radius` rounds the top corners.

## Connecting to Backend Data

The established pattern from `DashboardPage.jsx`:

```jsx
const [chartData, setChartData] = useState([]);

useEffect(() => {
  const fetchData = async () => {
    try {
      const res = await axios.get(`${API}/dashboard/revenue-chart?days=14`);
      setChartData(res.data.data); // Backend wraps in { data: [...] }
    } catch (error) {
      console.error("Failed to fetch chart data:", error);
    }
  };
  fetchData();
}, []);
```

**Key detail:** The backend returns `{ data: [...] }`, so chart data is at `res.data.data` (axios `.data` + response `.data`).

See the **fastapi** skill for adding new dashboard endpoints. See the **react** skill for the `useEffect` + axios pattern.

## Debugging Common Issues

### Chart renders but is empty
1. Check data: `console.log(chartData)` — is it `[]` or `undefined`?
2. Check `dataKey` props match exact object keys (case-sensitive)
3. Check values are numbers, not strings (`"45"` vs `45`)

### Chart is invisible (0 height)
1. Verify parent div has explicit height: `className="h-72"`
2. Verify `ResponsiveContainer` has `width="100%" height="100%"`

### Tooltip shows raw values
1. Add `formatter` to `<Tooltip>` for dollar formatting
2. Add `labelFormatter` for date formatting
3. Verify `contentStyle` overrides default white background

### Axes/grid invisible on dark background

Validate every component:
1. `<CartesianGrid stroke="#27272a" />`
2. `<XAxis stroke="#a1a1aa" tick={{ fill: '#a1a1aa' }} />`
3. `<YAxis stroke="#a1a1aa" tick={{ fill: '#a1a1aa' }} />`

If any of these are missing, the element renders with default colors invisible on dark backgrounds.

### Gradient not showing
1. Verify `<defs>` is inside the chart component, not outside
2. Verify gradient `id` matches the `fill="url(#id)"` exactly
3. Verify `fillOpacity={1}` on the `<Area>` — default may be less than 1
4. Check for duplicate gradient IDs if multiple charts exist on the page