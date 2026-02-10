# React Hook Form Hooks Reference

## Contents
- useForm Configuration
- useFormContext for Nested Components
- useWatch for Reactive Values
- useFieldArray for Dynamic Lists
- Anti-Patterns

## useForm Configuration

Every form starts with `useForm`. Always provide `resolver` and `defaultValues`:

```jsx
import { useForm } from "react-hook-form";
import { zodResolver } from "@hookform/resolvers/zod";
import { z } from "zod";

const schema = z.object({
  deposit_amount: z.coerce.number().min(0, "Must be positive").max(500),
  confirmation_window_hours: z.coerce.number().int().min(1).max(72),
});

function SettingsForm() {
  const form = useForm({
    resolver: zodResolver(schema),
    defaultValues: {
      deposit_amount: 20,
      confirmation_window_hours: 24,
    },
  });
}
```

### Key `formState` Properties

| Property | Type | Use |
|----------|------|-----|
| `isSubmitting` | boolean | Disable submit button, prevent double-submit |
| `isDirty` | boolean | Show "unsaved changes" warning |
| `errors` | object | Field-level errors (auto-displayed by `FormMessage`) |
| `isValid` | boolean | Only reliable with `mode: "onChange"` |

### Resetting from API Data

After fetching existing data (e.g., shop policy from `GET /api/shop/policy`), call `form.reset()`:

```jsx
useEffect(() => {
  async function load() {
    const { data } = await axios.get(`${API}/shop/policy`);
    form.reset({
      deposit_amount: data.deposit_amount,
      confirmation_window_hours: data.confirmation_window_hours,
      cancellation_window_hours: data.cancellation_window_hours,
      max_messages_per_day: data.max_messages_per_day,
    });
  }
  load();
}, [form]);
```

`reset()` clears `isDirty` and updates all field values. NEVER use `setValue` in a loop to populate forms — `reset` does it in one call.

## useFormContext for Nested Components

When a form spans multiple child components, wrap with `<Form>` (which is `FormProvider`) and access form methods via `useFormContext`:

```jsx
function ParentForm() {
  const form = useForm({ resolver: zodResolver(schema), defaultValues });

  return (
    <Form {...form}>
      <form onSubmit={form.handleSubmit(onSubmit)}>
        <DepositFields />
        <TimingFields />
        <Button type="submit">Save</Button>
      </form>
    </Form>
  );
}

function DepositFields() {
  const { control } = useFormContext();

  return (
    <FormField
      control={control}
      name="deposit_amount"
      render={({ field }) => (
        <FormItem>
          <FormLabel>Deposit Amount ($)</FormLabel>
          <FormControl>
            <Input type="number" step="0.01" {...field} />
          </FormControl>
          <FormMessage />
        </FormItem>
      )}
    />
  );
}
```

## useWatch for Reactive Values

Use `useWatch` to react to field changes without re-rendering the entire form. Common in this project for conditional fields:

```jsx
import { useWatch } from "react-hook-form";

function ConditionalDepositMessage({ control }) {
  const depositAmount = useWatch({ control, name: "deposit_amount" });

  if (depositAmount > 100) {
    return <p className="text-sm text-amber-400">High deposit may reduce bookings.</p>;
  }
  return null;
}
```

### WARNING: Using `watch()` Instead of `useWatch`

**The Problem:**

```jsx
// BAD - re-renders entire form on every keystroke
function SettingsForm() {
  const form = useForm({ ... });
  const depositAmount = form.watch("deposit_amount");
  // Every field change re-renders this component AND all children
}
```

**Why This Breaks:**
1. `watch()` subscribes to ALL form changes at the component level
2. Every keystroke in any field triggers a re-render of the entire tree
3. Expensive child components (charts, lists) re-render unnecessarily

**The Fix:**

```jsx
// GOOD - isolated subscription, only re-renders ConditionalMessage
<ConditionalDepositMessage control={form.control} />
```

## useFieldArray for Dynamic Lists

Use for repeatable field groups (e.g., adding multiple services to a booking):

```jsx
import { useFieldArray } from "react-hook-form";

function ServicesList() {
  const { control } = useFormContext();
  const { fields, append, remove } = useFieldArray({ control, name: "services" });

  return (
    <>
      {fields.map((field, index) => (
        <div key={field.id} className="flex gap-2">
          <FormField
            control={control}
            name={`services.${index}.service_id`}
            render={({ field }) => (
              <FormItem>
                <FormControl>
                  <Select onValueChange={field.onChange} defaultValue={field.value}>
                    <SelectTrigger><SelectValue /></SelectTrigger>
                    <SelectContent>{/* service options */}</SelectContent>
                  </Select>
                </FormControl>
                <FormMessage />
              </FormItem>
            )}
          />
          <Button variant="ghost" onClick={() => remove(index)}>Remove</Button>
        </div>
      ))}
      <Button variant="outline" onClick={() => append({ service_id: "" })}>
        Add Service
      </Button>
    </>
  );
}
```

NEVER use `index` as the `key` — always use `field.id` from `useFieldArray`. RHF generates stable IDs to preserve field state during reordering.

## Anti-Patterns

### WARNING: Calling `setValue` in onChange Handlers

**The Problem:**

```jsx
// BAD - fighting RHF's state management
<Input
  value={form.watch("name")}
  onChange={(e) => form.setValue("name", e.target.value)}
/>
```

**Why This Breaks:**
1. Bypasses RHF's built-in registration, losing validation triggers
2. Creates a controlled-uncontrolled hybrid that causes React warnings
3. `watch()` + `setValue` in the same component is a re-render loop

**The Fix:**

```jsx
// GOOD - use FormField which wraps Controller
<FormField
  control={form.control}
  name="name"
  render={({ field }) => (
    <FormControl><Input {...field} /></FormControl>
  )}
/>
```

**When You Might Be Tempted:** When migrating existing `useState` forms and trying to keep the old `onChange` pattern. Let `FormField` handle the binding.
