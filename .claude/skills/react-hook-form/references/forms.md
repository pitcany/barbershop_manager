# Forms Reference

## Contents
- Zod Schema Patterns
- Phone Number Validation
- Numeric Field Coercion
- Conditional Validation
- Multi-Step Form Pattern
- Form Migration Checklist
- Anti-Patterns

## Zod Schema Patterns

### Login Form

```jsx
const loginSchema = z.object({
  username: z.string().min(1, "Username is required"),
  password: z.string().min(1, "Password is required"),
});
```

### SMS Consent Form

```jsx
const smsConsentSchema = z.object({
  name: z.string().min(1, "Name is required"),
  phone: z.string()
    .min(1, "Phone number is required")
    .regex(/^\+\d{10,15}$/, "Enter a valid phone with country code (e.g. +15551234567)"),
  consent: z.literal(true, {
    errorMap: () => ({ message: "You must agree to receive SMS notifications" }),
  }),
});
```

Using `z.literal(true)` instead of `z.boolean()` ensures the checkbox MUST be checked. `z.boolean()` would accept `false`.

### Shop Policy Form

```jsx
const policySchema = z.object({
  deposit_amount: z.coerce.number().min(0, "Cannot be negative").max(500, "Maximum $500"),
  deposit_required_hours: z.coerce.number().int().min(1).max(168),
  confirmation_window_hours: z.coerce.number().int().min(1).max(72),
  cancellation_window_hours: z.coerce.number().int().min(1).max(48),
  max_messages_per_day: z.coerce.number().int().min(1).max(20),
});
```

### Booking Form

```jsx
const bookingSchema = z.object({
  client_name: z.string().min(1, "Name is required"),
  client_phone: z.string().regex(/^\+\d{10,15}$/, "Invalid phone format"),
  barber_id: z.string().min(1, "Select a barber"),
  service_id: z.string().min(1, "Select a service"),
  date: z.string().min(1, "Select a date"),
  time: z.string().min(1, "Select a time"),
});
```

## Phone Number Validation

The project has a phone formatting function in SMSConsentPage. Reuse this with Zod's `transform`:

```jsx
const phoneSchema = z.string()
  .min(1, "Phone is required")
  .transform((val) => {
    const digits = val.replace(/\D/g, "");
    if (digits.length === 10) return `+1${digits}`;
    if (digits.length === 11 && digits.startsWith("1")) return `+${digits}`;
    return val.startsWith("+") ? val : `+${digits}`;
  })
  .pipe(z.string().regex(/^\+\d{10,15}$/, "Invalid phone number"));
```

`transform` + `pipe` lets you normalize first, then validate the normalized value.

## Numeric Field Coercion

HTML `<input type="number">` always produces a string. Use `z.coerce.number()`:

```jsx
// Schema
deposit_amount: z.coerce.number().min(0).max(500),

// This handles: "20" → 20, "0" → 0, "" → NaN (fails validation)
```

### WARNING: Using `z.number()` Without Coerce

**The Problem:**

```jsx
// BAD - z.number() expects a number, but <Input> gives a string
const schema = z.object({
  deposit_amount: z.number().min(0),
});
```

**Why This Breaks:**
1. `<Input type="number">` produces `"20"` (a string), not `20`
2. `z.number()` rejects strings — validation always fails with "Expected number, received string"
3. The user sees a confusing error on a perfectly valid input

**The Fix:**

```jsx
// GOOD - z.coerce.number() converts string to number first
deposit_amount: z.coerce.number().min(0),
```

## Conditional Validation

Use `z.discriminatedUnion` or `.superRefine` for fields that depend on other fields:

```jsx
// Deposit is required only when deposit_required_hours > 0
const policySchema = z.object({
  deposit_required_hours: z.coerce.number().int().min(0),
  deposit_amount: z.coerce.number().min(0),
}).refine(
  (data) => data.deposit_required_hours === 0 || data.deposit_amount > 0,
  {
    message: "Deposit amount must be greater than $0 when deposits are enabled",
    path: ["deposit_amount"],
  }
);
```

The `path` option tells RHF which field to display the error on.

## Multi-Step Form Pattern

For complex forms (e.g., booking flow: client → service → time → confirm):

```jsx
const [step, setStep] = useState(0);
const form = useForm({
  resolver: zodResolver(bookingSchema),
  defaultValues: { client_name: "", client_phone: "", barber_id: "", service_id: "", date: "", time: "" },
});

const nextStep = async () => {
  const fieldsPerStep = [
    ["client_name", "client_phone"],
    ["barber_id", "service_id"],
    ["date", "time"],
  ];
  const valid = await form.trigger(fieldsPerStep[step]);
  if (valid) setStep((s) => s + 1);
};
```

`form.trigger(fieldNames)` validates only the specified fields and returns a boolean. Validate per step without submitting the full form.

## Form Migration Checklist

When converting an existing `useState` form to RHF + Zod:

Copy this checklist and track progress:
- [ ] Step 1: Identify all `useState` calls that hold field values
- [ ] Step 2: Write a Zod schema matching those fields (use `snake_case` keys to match API)
- [ ] Step 3: Replace `useState` with `useForm({ resolver: zodResolver(schema), defaultValues })`
- [ ] Step 4: Replace `<form onSubmit={(e) => { e.preventDefault(); ... }}>` with `<Form {...form}><form onSubmit={form.handleSubmit(onSubmit)}>`
- [ ] Step 5: Replace each `<Input value={x} onChange={...} />` with `<FormField>` pattern
- [ ] Step 6: Remove manual `setLoading` — use `form.formState.isSubmitting`
- [ ] Step 7: Remove manual validation checks (e.g., `if (!formData.consent)`) — Zod handles this
- [ ] Step 8: Add `<FormMessage />` inside each `<FormItem>` for field-level errors
- [ ] Step 9: Test: submit empty form, verify Zod errors appear inline
- [ ] Step 10: Test: submit valid form, verify API call works

Iterate-until-pass validation:
1. Submit the form with empty/invalid data
2. Check that inline error messages appear next to the correct fields
3. If errors are missing or misplaced, verify `name` prop matches schema key
4. Fix and repeat until all validation errors display correctly

## Anti-Patterns

### WARNING: Validating Manually Instead of Using Zod

**The Problem:**

```jsx
// BAD - manual validation before submit
const handleSubmit = async (e) => {
  e.preventDefault();
  if (!formData.consent) {
    toast.error("Please agree to receive SMS notifications");
    return;
  }
  if (!formData.phone.match(/^\+\d{10,15}$/)) {
    toast.error("Invalid phone number");
    return;
  }
  // ... submit
};
```

**Why This Breaks:**
1. Validation logic is scattered across the submit handler instead of centralized in a schema
2. Error messages go to toast instead of inline next to the field
3. Only validates on submit — no real-time feedback as the user types
4. Every new field needs a new `if` statement — scales poorly

**The Fix:**

```jsx
// GOOD - centralized in Zod schema, displayed inline via FormMessage
const schema = z.object({
  phone: z.string().regex(/^\+\d{10,15}$/, "Invalid phone number"),
  consent: z.literal(true, { errorMap: () => ({ message: "Consent is required" }) }),
});
// handleSubmit only fires when ALL validation passes
```

See the **pydantic** skill for the backend validation that mirrors these Zod schemas.
