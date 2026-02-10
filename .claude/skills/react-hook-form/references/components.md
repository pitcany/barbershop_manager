# Form Components Reference

## Contents
- shadcn/ui Form Component Tree
- Component Composition Pattern
- Integrating shadcn/ui Input Components
- Migrating Existing useState Forms
- Checklist: Adding a New Form

## shadcn/ui Form Component Tree

The form components live at `frontend/src/components/ui/form.jsx`. They wrap RHF's `Controller` and `FormProvider`:

| Component | Wraps | Purpose |
|-----------|-------|---------|
| `Form` | `FormProvider` | Provides form context to all children |
| `FormField` | `Controller` | Connects a field name to RHF control |
| `FormItem` | `div` | Groups label + input + message, generates `id` |
| `FormLabel` | `Label` | Auto-colors red on error via `useFormField()` |
| `FormControl` | `Slot` | Sets `aria-invalid`, `aria-describedby` |
| `FormMessage` | `p` | Renders `error.message` from Zod, auto-hides if no error |
| `FormDescription` | `p` | Helper text below field (optional) |

## Component Composition Pattern

Every form field follows this exact structure:

```jsx
<FormField
  control={form.control}
  name="field_name"
  render={({ field }) => (
    <FormItem>
      <FormLabel>Field Label</FormLabel>
      <FormControl>
        <Input {...field} className="bg-input/50 border-input" />
      </FormControl>
      <FormDescription>Optional help text</FormDescription>
      <FormMessage />
    </FormItem>
  )}
/>
```

`FormMessage` is always last inside `FormItem`. It renders nothing when there is no error.

## Integrating shadcn/ui Input Components

### Text Input

```jsx
<FormField
  control={form.control}
  name="name"
  render={({ field }) => (
    <FormItem>
      <FormLabel>Client Name</FormLabel>
      <FormControl>
        <Input placeholder="Enter name" {...field} className="bg-input/50 border-input" />
      </FormControl>
      <FormMessage />
    </FormItem>
  )}
/>
```

### Number Input

Use `z.coerce.number()` in the schema — HTML inputs always produce strings:

```jsx
// Schema
const schema = z.object({
  deposit_amount: z.coerce.number().min(0).max(500),
});

// Field
<FormField
  control={form.control}
  name="deposit_amount"
  render={({ field }) => (
    <FormItem>
      <FormLabel>Deposit Amount ($)</FormLabel>
      <FormControl>
        <Input type="number" step="0.01" {...field} className="bg-input/50 border-input" />
      </FormControl>
      <FormMessage />
    </FormItem>
  )}
/>
```

### Select (shadcn/ui)

Radix Select uses `onValueChange` instead of `onChange`. Spread `field` manually:

```jsx
<FormField
  control={form.control}
  name="status"
  render={({ field }) => (
    <FormItem>
      <FormLabel>Status</FormLabel>
      <Select onValueChange={field.onChange} defaultValue={field.value}>
        <FormControl>
          <SelectTrigger className="bg-input/50 border-input">
            <SelectValue placeholder="Select status" />
          </SelectTrigger>
        </FormControl>
        <SelectContent>
          <SelectItem value="confirmed">Confirmed</SelectItem>
          <SelectItem value="cancelled">Cancelled</SelectItem>
        </SelectContent>
      </Select>
      <FormMessage />
    </FormItem>
  )}
/>
```

### Checkbox

```jsx
<FormField
  control={form.control}
  name="consent"
  render={({ field }) => (
    <FormItem className="flex flex-row items-start space-x-3 space-y-0">
      <FormControl>
        <Checkbox checked={field.value} onCheckedChange={field.onChange} />
      </FormControl>
      <div className="space-y-1 leading-none">
        <FormLabel>I agree to receive SMS notifications</FormLabel>
        <FormDescription>You can opt out at any time by texting STOP.</FormDescription>
      </div>
      <FormMessage />
    </FormItem>
  )}
/>
```

### Textarea

```jsx
<FormField
  control={form.control}
  name="message"
  render={({ field }) => (
    <FormItem>
      <FormLabel>Message</FormLabel>
      <FormControl>
        <Textarea placeholder="Type your message" {...field} className="bg-input/50 border-input" />
      </FormControl>
      <FormMessage />
    </FormItem>
  )}
/>
```

## WARNING: Mixing useState with FormField

**The Problem:**

```jsx
// BAD - maintaining parallel state
const [name, setName] = useState("");

<FormField
  control={form.control}
  name="name"
  render={({ field }) => (
    <Input
      value={name}  // Overrides RHF value
      onChange={(e) => { setName(e.target.value); field.onChange(e); }}
      {...field}
    />
  )}
/>
```

**Why This Breaks:**
1. Two sources of truth — `name` state and RHF's internal state can diverge
2. `form.reset()` updates RHF but not `useState`, creating stale UI
3. Validation runs on RHF's value, but the user sees `useState`'s value

**The Fix:** Remove the `useState` entirely. RHF manages the value through `field`.

## Migrating Existing useState Forms

This project's pages (LoginPage, SMSConsentPage, SettingsPage) all use `useState`. To migrate:

Copy this checklist and track progress:
- [ ] Step 1: Define a Zod schema matching the current `useState` shape
- [ ] Step 2: Replace `useState` with `useForm({ resolver: zodResolver(schema), defaultValues })`
- [ ] Step 3: Wrap the `<form>` with `<Form {...form}>`
- [ ] Step 4: Replace `onSubmit={(e) => { e.preventDefault(); ... }}` with `onSubmit={form.handleSubmit(onSubmit)}`
- [ ] Step 5: Replace each `<Input value={x} onChange={...} />` with a `<FormField>` block
- [ ] Step 6: Remove all `useState` for form fields and `setLoading` (use `isSubmitting`)
- [ ] Step 7: Verify field names match `snake_case` API keys exactly

### Migration Example: LoginPage

Before (current):
```jsx
const [username, setUsername] = useState("");
const [password, setPassword] = useState("");
const [loading, setLoading] = useState(false);

const handleSubmit = async (e) => {
  e.preventDefault();
  setLoading(true);
  try {
    await login(username, password);
  } catch (error) {
    toast.error(error.response?.data?.detail || "Login failed");
  } finally {
    setLoading(false);
  }
};
```

After:
```jsx
const loginSchema = z.object({
  username: z.string().min(1, "Username is required"),
  password: z.string().min(1, "Password is required"),
});

const form = useForm({
  resolver: zodResolver(loginSchema),
  defaultValues: { username: "", password: "" },
});

const onSubmit = async (data) => {
  try {
    await login(data.username, data.password);
  } catch (error) {
    toast.error(error.response?.data?.detail || "Login failed");
  }
};
// Use form.formState.isSubmitting instead of loading state
```

See the **tailwind** skill for styling form fields with the project's dark theme.
See the **react** skill for component structure and Context API patterns.
