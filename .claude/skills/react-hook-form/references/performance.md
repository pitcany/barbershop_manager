# Performance Reference

## Contents
- Why RHF is Fast by Default
- Isolating Re-Renders with useWatch
- Expensive Computations in Forms
- FormField Render Optimization
- Lazy-Loaded Form Modals
- Anti-Patterns

## Why RHF is Fast by Default

React Hook Form uses uncontrolled inputs internally. Unlike `useState`-driven forms where every keystroke re-renders the component tree, RHF only re-renders when:
- `formState` properties you access change (errors, isSubmitting, isDirty)
- You call `watch()` or `useWatch()`
- Validation runs and changes error state

This is why migrating from `useState` to RHF improves performance for free — especially on SettingsPage with 5 numeric inputs.

## Isolating Re-Renders with useWatch

Use `useWatch` in a child component to subscribe to specific fields without re-rendering the parent:

```jsx
// GOOD - only PricePreview re-renders when deposit_amount changes
function SettingsForm() {
  const form = useForm({ resolver: zodResolver(policySchema), defaultValues });

  return (
    <Form {...form}>
      <form onSubmit={form.handleSubmit(onSubmit)} className="space-y-6">
        <FormField control={form.control} name="deposit_amount" render={/* ... */} />
        <FormField control={form.control} name="confirmation_window_hours" render={/* ... */} />
        <PricePreview control={form.control} />
      </form>
    </Form>
  );
}

function PricePreview({ control }) {
  const deposit = useWatch({ control, name: "deposit_amount" });
  return (
    <Card className="bg-card/50">
      <p className="text-sm font-mono text-muted-foreground">
        Client will pay: ${Number(deposit || 0).toFixed(2)}
      </p>
    </Card>
  );
}
```

### WARNING: Using `watch()` at the Form Level

**The Problem:**

```jsx
// BAD - every field change re-renders the entire form
function SettingsForm() {
  const form = useForm({ ... });
  const allValues = form.watch(); // Subscribes to EVERYTHING

  return (
    <div>
      <ExpensiveField1 />
      <ExpensiveField2 />
      <p>Deposit: {allValues.deposit_amount}</p>
    </div>
  );
}
```

**Why This Breaks:**
1. `watch()` without arguments subscribes to all form values
2. Typing in ANY field re-renders the parent AND all children
3. If children include lists, selects with many options, or charts, the UI stutters

**The Fix:**

```jsx
// GOOD - subscribe to exactly what you need, in an isolated component
function DepositDisplay({ control }) {
  const deposit = useWatch({ control, name: "deposit_amount" });
  return <p>Deposit: {deposit}</p>;
}
```

## Expensive Computations in Forms

If a form-derived value requires heavy computation (rare in this project, but possible for pricing calculations):

```jsx
import { useMemo } from "react";
import { useWatch } from "react-hook-form";

function PricingSummary({ control, services }) {
  const selectedServiceId = useWatch({ control, name: "service_id" });

  // Only recompute when selection changes
  const serviceDetails = useMemo(() => {
    return services.find((s) => s.id === selectedServiceId);
  }, [selectedServiceId, services]);

  if (!serviceDetails) return null;

  return (
    <div className="text-sm text-muted-foreground">
      <p>{serviceDetails.name} — ${serviceDetails.price}</p>
      <p>Duration: {serviceDetails.duration_minutes} min</p>
    </div>
  );
}
```

## FormField Render Optimization

The `render` prop in `FormField` creates a new function every render. This is fine — React's reconciliation handles it efficiently. NEVER wrap `render` in `useCallback`:

```jsx
// BAD - useCallback adds overhead without benefit here
const renderName = useCallback(({ field }) => (
  <FormItem>
    <FormLabel>Name</FormLabel>
    <FormControl><Input {...field} /></FormControl>
    <FormMessage />
  </FormItem>
), []);

// GOOD - inline render prop, simple and clear
<FormField
  control={form.control}
  name="name"
  render={({ field }) => (
    <FormItem>
      <FormLabel>Name</FormLabel>
      <FormControl><Input {...field} /></FormControl>
      <FormMessage />
    </FormItem>
  )}
/>
```

The `Controller` (which `FormField` wraps) already optimizes re-renders internally. Adding `useCallback` just adds code without improving performance.

## Lazy-Loaded Form Modals

For forms inside modals that aren't visible at page load, lazy-load the modal content:

```jsx
import { lazy, Suspense } from "react";
import { Dialog, DialogContent, DialogTrigger } from "@/components/ui/dialog";

const BookingForm = lazy(() => import("./BookingForm"));

function BookingButton() {
  return (
    <Dialog>
      <DialogTrigger asChild>
        <Button>New Booking</Button>
      </DialogTrigger>
      <DialogContent>
        <Suspense fallback={<Skeleton className="h-64" />}>
          <BookingForm />
        </Suspense>
      </DialogContent>
    </Dialog>
  );
}
```

The Zod schema, `useForm`, and all form field components only load when the dialog opens. Keeps the initial page bundle smaller.

## Anti-Patterns

### WARNING: Re-Rendering the Whole Page on Validation

**The Problem:**

```jsx
// BAD - mode: "all" with formState at the page level
const form = useForm({
  resolver: zodResolver(schema),
  mode: "all", // Validates on every change AND blur
});

// Destructuring errors at page level subscribes the whole page
const { errors } = form.formState;
```

**Why This Breaks:**
1. `mode: "all"` runs validation on every keystroke AND blur
2. Destructuring `errors` at the page level re-renders the page on every error change
3. Combined: every keystroke triggers validation → error state changes → full page re-render

**The Fix:**

```jsx
// GOOD - default mode, let FormMessage handle errors
const form = useForm({
  resolver: zodResolver(schema),
  // mode: "onSubmit" is the default — validates on submit only
});

// FormMessage reads errors internally via useFormField()
// No need to destructure errors at the parent level
<FormField
  control={form.control}
  name="phone"
  render={({ field }) => (
    <FormItem>
      <FormControl><Input {...field} /></FormControl>
      <FormMessage /> {/* Handles its own error subscription */}
    </FormItem>
  )}
/>
```

If you need real-time validation feedback, use `mode: "onBlur"` — validates when the user leaves the field, not on every keystroke.

### WARNING: Creating Forms Inside Loops

**The Problem:**

```jsx
// BAD - new useForm per list item
{appointments.map((apt) => {
  const form = useForm({ defaultValues: apt }); // Violates Rules of Hooks
  return <AppointmentForm key={apt.id} form={form} />;
})}
```

**Why This Breaks:** Hooks cannot be called inside loops. React will throw an error.

**The Fix:** Move `useForm` inside the child component:

```jsx
{appointments.map((apt) => (
  <AppointmentForm key={apt.id} defaultValues={apt} />
))}

function AppointmentForm({ defaultValues }) {
  const form = useForm({ resolver: zodResolver(schema), defaultValues });
  // ...
}
```

See the **react** skill for general React performance patterns (React.memo, useMemo, code splitting).
See the **tailwind** skill for minimizing CSS class computation overhead.
