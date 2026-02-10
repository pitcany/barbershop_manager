# Layouts Reference

## Contents
- Page Shell
- Grid Systems
- Responsive Sidebar
- Content Containers
- Responsive Breakpoints
- Split Panels
- WARNING: Fixed Heights

## Page Shell

Every authenticated page wraps content in `Layout`:

```jsx
import Layout from "../components/layout/Layout";

export default function SomePage() {
  return (
    <Layout title="Page Title">
      <div className="space-y-6">
        {/* Page content */}
      </div>
    </Layout>
  );
}
```

Layout provides:
- Responsive sidebar with navigation
- Mobile hamburger menu with overlay
- Page title in mobile header
- Content area with `p-6 lg:p-8` padding

## Grid Systems

### Dashboard Stats Grid (4 columns)

```jsx
<div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-6">
  <StatCard title="Revenue" value="$2,450" icon={DollarSign} />
  <StatCard title="Appointments" value="24" icon={Calendar} />
  <StatCard title="No-Shows" value="2" icon={AlertTriangle} />
  <StatCard title="Waitlist" value="8" icon={Users} />
</div>
```

### Card Grid (3 columns)

```jsx
<div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-6">
  {items.map(item => <ItemCard key={item.id} {...item} />)}
</div>
```

### Two-Column Content

```jsx
<div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
  <Card>{/* Left panel */}</Card>
  <Card>{/* Right panel */}</Card>
</div>
```

## Responsive Sidebar

The sidebar pattern from `frontend/src/components/layout/Layout.jsx`:

```jsx
{/* Sidebar — hidden on mobile, fixed width on desktop */}
<aside className={`
  fixed inset-y-0 left-0 z-40 w-64
  bg-card border-r border-border
  transform transition-transform duration-300 ease-in-out
  ${sidebarOpen ? "translate-x-0" : "-translate-x-full"}
  lg:translate-x-0 lg:static lg:block
`}>
  {/* Logo */}
  <div className="flex items-center gap-2 px-6 py-6 border-b border-border">
    <Scissors className="w-6 h-6 text-primary" />
    <span className="font-heading text-lg font-semibold">Barbershop</span>
  </div>

  {/* Nav links */}
  <nav className="mt-6 space-y-1">
    {navItems.map(item => (
      <NavLink
        key={item.path}
        to={item.path}
        className={({ isActive }) => `
          flex items-center gap-3 px-6 py-3 text-sm font-medium
          transition-colors duration-200
          ${isActive
            ? "bg-primary/10 text-primary border-r-2 border-primary"
            : "text-muted-foreground hover:text-foreground hover:bg-accent/50"
          }
        `}
      >
        <item.icon className="w-5 h-5" />
        {item.label}
      </NavLink>
    ))}
  </nav>
</aside>

{/* Mobile overlay */}
{sidebarOpen && (
  <div
    className="fixed inset-0 z-30 bg-black/50 lg:hidden"
    onClick={() => setSidebarOpen(false)}
  />
)}
```

## Content Containers

### Standard Page Content

```jsx
<div className="space-y-6">
  {/* Header row with title and actions */}
  <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-4">
    <h2 className="font-heading font-semibold text-2xl">Section Title</h2>
    <div className="flex items-center gap-2">
      <Button variant="outline" size="sm">Filter</Button>
      <Button size="sm">Add New</Button>
    </div>
  </div>

  {/* Content area */}
  <Card>
    <CardContent className="p-6">{/* ... */}</CardContent>
  </Card>
</div>
```

### Filter Bar

```jsx
<div className="flex flex-wrap items-center gap-3">
  <Select onValueChange={setStatusFilter}>
    <SelectTrigger className="w-40" data-testid="status-filter">
      <SelectValue placeholder="All statuses" />
    </SelectTrigger>
    <SelectContent>{/* options */}</SelectContent>
  </Select>
  {hasActiveFilters && (
    <Button variant="ghost" size="sm" onClick={clearFilters}>
      <X className="w-4 h-4 mr-1" /> Clear
    </Button>
  )}
</div>
```

## Responsive Breakpoints

The project uses Tailwind's default breakpoints:

| Breakpoint | Width | Usage |
|-----------|-------|-------|
| (base) | 0px | Single column, mobile menu |
| `md` | 768px | 2-column grids |
| `lg` | 1024px | Full sidebar, 3-4 column grids |

Common responsive patterns:

```jsx
// Grid expansion
className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-6"

// Padding scaling
className="p-6 md:p-8 lg:p-12"

// Show/hide
className="hidden lg:block"     // Desktop only
className="lg:hidden"           // Mobile only

// Stack to row
className="flex flex-col sm:flex-row sm:items-center gap-4"
```

## Split Panels

Conversations page uses a master-detail split:

```jsx
<div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
  {/* List panel — 1 column */}
  <Card className="lg:col-span-1">
    <div className="h-[calc(100vh-200px)] overflow-y-auto">
      {conversations.map(c => <ConversationItem key={c.id} {...c} />)}
    </div>
  </Card>

  {/* Detail panel — 2 columns */}
  <Card className="lg:col-span-2">
    <div className="h-[calc(100vh-200px)] flex flex-col">
      <div className="flex-1 overflow-y-auto p-4">{/* Messages */}</div>
      <div className="border-t border-border p-4">{/* Input */}</div>
    </div>
  </Card>
</div>
```

## WARNING: Fixed Heights Without Viewport Calc

**The Problem:**

```jsx
// BAD — arbitrary fixed height
<div className="h-96 overflow-y-auto">
```

**Why This Breaks:**
1. Doesn't adapt to different screen sizes
2. Creates double scrollbars on smaller viewports
3. Leaves wasted space on larger screens

**The Fix:**

```jsx
// GOOD — viewport-relative with offset for header/nav
<div className="h-[calc(100vh-200px)] overflow-y-auto">
```

**When You Might Be Tempted:** Any scrollable list or panel. Always use `calc(100vh - Xpx)` where X accounts for the Layout header, padding, and any fixed elements above the scroll container.
