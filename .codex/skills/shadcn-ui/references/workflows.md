# shadcn/ui Workflows Reference

## Contents
- Adding New Components
- Form Integration
- Toast Notifications
- Testing UI Components
- Design System Compliance

## Adding New Components

### Install via CLI

```bash
cd frontend && npx shadcn@latest add [component-name]
```

The CLI reads `frontend/components.json` and generates a `.jsx` file (not `.tsx`) in `src/components/ui/`.

### Post-Install Checklist

Copy this checklist and track progress:
- [ ] Step 1: Run `npx shadcn@latest add [name]` from `frontend/`
- [ ] Step 2: Verify file created at `src/components/ui/[name].jsx`
- [ ] Step 3: Check imports use `@/lib/utils` and `@/components/ui/` paths
- [ ] Step 4: Verify `cn()` is used for all className merging
- [ ] Step 5: Add `data-testid` attributes to interactive elements
- [ ] Step 6: Test component renders in dark theme (gold primary, near-black background)

### WARNING: Installing TSX Components in JSX Project

**The Problem:**
```bash
# BAD — generates .tsx files, project uses .jsx
npx shadcn@latest add button  # without components.json tsx:false
```

**Why This Breaks:** Build fails — CRACO/CRA doesn't process `.tsx` without TypeScript config.

**The Fix:** Ensure `frontend/components.json` has `"tsx": false` before running CLI. The existing config is correct; don't modify it.

## Form Integration

Forms use React Hook Form + Zod + shadcn Form components. See the **react-hook-form** skill for full patterns.

### Basic Form Field

```jsx
import { Form, FormControl, FormField, FormItem, FormLabel, FormMessage } from "@/components/ui/form";
import { Input } from "@/components/ui/input";

<FormField
  control={form.control}
  name="deposit_amount"
  render={({ field }) => (
    <FormItem>
      <FormLabel>Deposit Amount ($)</FormLabel>
      <FormControl>
        <Input type="number" className="bg-input/50 border-input" {...field} />
      </FormControl>
      <FormMessage />
    </FormItem>
  )}
/>
```

### Simple Controlled Form (Without React Hook Form)

Settings page uses direct state management:

```jsx
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Button } from "@/components/ui/button";
import { Separator } from "@/components/ui/separator";
import { Save } from "lucide-react";

<div className="space-y-2">
  <Label htmlFor="deposit_amount">Deposit Amount ($)</Label>
  <Input
    id="deposit_amount"
    type="number"
    value={formData.deposit_amount}
    onChange={(e) => setFormData(prev => ({ ...prev, deposit_amount: parseFloat(e.target.value) }))}
    className="bg-input/50 border-input"
  />
</div>
<Separator />
<Button onClick={handleSave} disabled={saving}>
  <Save className="w-4 h-4 mr-2" />
  {saving ? "Saving..." : "Save Settings"}
</Button>
```

**When to use which:** React Hook Form + Zod for complex forms with validation. Direct `useState` for simple settings with few fields.

## Toast Notifications

This project uses **Sonner** for all toasts. The Radix toast system (`toast.jsx`, `toaster.jsx`, `use-toast.js`) exists but is NOT actively used.

### Setup (Already Configured)

```jsx
// App.js
import { Toaster } from "sonner";

<Toaster position="top-right" richColors />
```

### Usage in Pages

```jsx
import { toast } from "sonner";

const handleSave = async () => {
  try {
    await axios.patch(`${API}/shop/policy`, formData);
    toast.success("Settings saved successfully");
  } catch (error) {
    toast.error("Failed to save settings");
  }
};
```

### WARNING: Using Radix Toast Instead of Sonner

**The Problem:**
```jsx
// BAD — project uses Sonner, not the Radix toast hook
import { useToast } from "@/hooks/use-toast";
const { toast } = useToast();
toast({ title: "Saved" });
```

**Why This Breaks:** Two competing toast systems. The Radix `<Toaster>` isn't mounted in `App.js` — only Sonner's is. Radix toasts silently fail to render.

**The Fix:**
```jsx
// GOOD — import directly from sonner
import { toast } from "sonner";
toast.success("Saved");
toast.error("Failed");
```

## Testing UI Components

All interactive elements should include `data-testid` attributes:

```jsx
<SelectTrigger className="w-48 bg-input/50" data-testid="status-filter">
  <SelectValue placeholder="Filter by status" />
</SelectTrigger>

<Button data-testid="save-settings" onClick={handleSave}>Save</Button>
```

### Validation Loop

1. Make UI changes
2. Validate: `cd frontend && yarn build`
3. If build fails, fix JSX/import errors and repeat step 2
4. Only proceed when build passes
5. Visually verify in browser at `http://localhost:3000`

## Design System Compliance

The design system is defined in `design_guidelines.json`. Key rules for shadcn components:

### Color Tokens (NEVER Hardcode)

| Purpose | Token | Resolves To |
|---------|-------|-------------|
| Page background | `bg-background` | Near-black #09090b |
| Card surface | `bg-card` | Dark #18181b |
| Primary action | `bg-primary` | Gold #D4AF37 |
| Borders | `border-border` | #27272a |
| Muted text | `text-muted-foreground` | Gray |
| Focus ring | `ring-ring` | Gold #D4AF37 |

### Typography in Components

```jsx
// Headings — Playfair Display
<CardTitle className="font-heading text-lg">Revenue</CardTitle>

// Body text — Inter (default, no class needed)
<p className="text-sm text-muted-foreground">Description</p>

// Numbers/money — JetBrains Mono
<span className="font-mono text-2xl">$1,250.00</span>
```

### Opacity Modifiers

Use Tailwind's `/` opacity syntax for subtle backgrounds:

```jsx
// Icon container: 10% opacity background
<div className="bg-emerald-500/10">

// Hover states: 50% opacity accent
<TableRow className="hover:bg-accent/30">

// Active nav: 10% primary tint
<a className="bg-primary/10 text-primary">
```

### WARNING: Using `shadow-lg` or Heavy Shadows

**The Problem:**
```jsx
// BAD — violates "Old Money Tech" aesthetic
<Card className="shadow-lg shadow-xl">
```

**The Fix:**
```jsx
// GOOD — subtle shadow only, per design_guidelines.json
<Card className="shadow-sm">
// Or no shadow at all — borders provide sufficient separation
<Card className="border border-border">
```

The design system specifies `shadow-sm` maximum. Heavy shadows conflict with the dark theme and premium aesthetic. See the **tailwind** skill for full styling conventions.