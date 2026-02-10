# shadcn/ui Patterns Reference

## Contents
- Component Composition
- Radix Primitive Wrapping
- Variant System with CVA
- The cn() Helper
- Anti-Patterns

## Component Composition

shadcn/ui components are compositional — build complex UI by nesting simple parts.

### Multi-Part Component Usage

```jsx
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "@/components/ui/table";

<Card>
  <CardHeader>
    <CardTitle className="font-heading">Appointments</CardTitle>
  </CardHeader>
  <CardContent>
    <Table>
      <TableHeader>
        <TableRow className="border-border hover:bg-transparent">
          <TableHead className="text-muted-foreground">Client</TableHead>
          <TableHead className="text-muted-foreground">Status</TableHead>
        </TableRow>
      </TableHeader>
      <TableBody>
        {items.map((item) => (
          <TableRow key={item.id} className="border-border hover:bg-accent/30">
            <TableCell>{item.name}</TableCell>
            <TableCell><Badge className={statusColors[item.status]}>{item.status}</Badge></TableCell>
          </TableRow>
        ))}
      </TableBody>
    </Table>
  </CardContent>
</Card>
```

### Select with Controlled State

```jsx
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";

<Select value={statusFilter} onValueChange={setStatusFilter}>
  <SelectTrigger className="w-48 bg-input/50">
    <SelectValue placeholder="Filter by status" />
  </SelectTrigger>
  <SelectContent>
    {options.map((opt) => (
      <SelectItem key={opt.value} value={opt.value}>{opt.label}</SelectItem>
    ))}
  </SelectContent>
</Select>
```

## Radix Primitive Wrapping

Complex interactive components wrap Radix UI primitives. The pattern:

```jsx
import * as DialogPrimitive from "@radix-ui/react-dialog";
import { cn } from "@/lib/utils";
import { X } from "lucide-react";

const Dialog = DialogPrimitive.Root;
const DialogTrigger = DialogPrimitive.Trigger;

const DialogContent = React.forwardRef(({ className, children, ...props }, ref) => (
  <DialogPrimitive.Portal>
    <DialogPrimitive.Overlay className="fixed inset-0 z-50 bg-black/80 data-[state=open]:animate-in" />
    <DialogPrimitive.Content
      ref={ref}
      className={cn("fixed left-[50%] top-[50%] z-50 ...", className)}
      {...props}
    >
      {children}
      <DialogPrimitive.Close className="absolute right-4 top-4">
        <X className="h-4 w-4" />
      </DialogPrimitive.Close>
    </DialogPrimitive.Content>
  </DialogPrimitive.Portal>
));
```

**Key rules:**
- Always forward `ref` and spread `...props`
- Always merge `className` with `cn()`
- Portal rendering for overlays/dropdowns (z-index isolation)
- Radix `data-[state=*]` attributes drive animations

### WARNING: Overriding Radix Behavior

**The Problem:**
```jsx
// BAD — breaks keyboard nav, ARIA, focus management
<div onClick={closeDialog} onKeyDown={handleEsc} role="dialog">
```

**Why This Breaks:**
1. Radix handles focus trapping, Escape key, click-outside automatically
2. Manual reimplementation misses edge cases (screen readers, nested dialogs)
3. ARIA attributes are incomplete without Radix state management

**The Fix:**
```jsx
// GOOD — let Radix manage behavior, you manage styling
<DialogContent className="custom-styles">
  {children}
</DialogContent>
```

## Variant System with CVA

Button is the canonical example of class-variance-authority:

```jsx
import { cva } from "class-variance-authority";

const buttonVariants = cva(
  "inline-flex items-center justify-center gap-2 whitespace-nowrap rounded-md text-sm font-medium transition-colors",
  {
    variants: {
      variant: {
        default: "bg-primary text-primary-foreground shadow hover:bg-primary/90",
        destructive: "bg-destructive text-destructive-foreground shadow-sm hover:bg-destructive/90",
        outline: "border border-input bg-background shadow-sm hover:bg-accent hover:text-accent-foreground",
        ghost: "hover:bg-accent hover:text-accent-foreground",
        link: "text-primary underline-offset-4 hover:underline",
      },
      size: {
        default: "h-9 px-4 py-2",
        sm: "h-8 rounded-md px-3 text-xs",
        lg: "h-10 rounded-md px-8",
        icon: "h-9 w-9",
      },
    },
    defaultVariants: { variant: "default", size: "default" },
  }
);
```

**Usage:** `<Button variant="outline" size="sm">` or export `buttonVariants` for non-Button elements needing button styling.

## The cn() Helper

```jsx
import { clsx } from "clsx";
import { twMerge } from "tailwind-merge";

export function cn(...inputs) {
  return twMerge(clsx(inputs));
}
```

`clsx` handles conditionals. `twMerge` resolves Tailwind conflicts (last wins). Every shadcn component uses this.

```jsx
// Conditional classes
<div className={cn("base-styles", isActive && "bg-primary/10", className)} />
```

### WARNING: String Concatenation Instead of cn()

**The Problem:**
```jsx
// BAD — Tailwind conflicts not resolved, conditional classes messy
<div className={`p-4 ${isActive ? "bg-primary p-6" : ""} ${className}`} />
```

**Why This Breaks:**
1. `p-4` and `p-6` both apply — unpredictable result
2. Empty strings produce extra spaces
3. No deduplication of identical utilities

**The Fix:**
```jsx
// GOOD — twMerge resolves p-4 vs p-6, clsx handles conditionals
<div className={cn("p-4", isActive && "bg-primary p-6", className)} />
```

## Anti-Patterns

### WARNING: Importing from Wrong Path

```jsx
// BAD — breaks @/ alias convention
import { Button } from "../../components/ui/button";
import { Button } from "../components/ui/button";

// GOOD — consistent alias usage
import { Button } from "@/components/ui/button";
```

**Exception:** Page components in `frontend/src/pages/` currently use relative imports (`"../components/ui/button"`). New code should prefer `@/` aliases.

### WARNING: Using Default Exports for UI Components

```jsx
// BAD — shadcn convention is named exports
export default function Button({ ... }) { }

// GOOD — named exports enable tree-shaking and multi-part imports
export { Button, buttonVariants }
```

Page components (`DashboardPage.jsx`) use default exports. UI primitives use named exports. Don't mix these conventions.