# State Management Reference

## Contents
- Form State vs UI State
- RHF Internal State
- Connecting to Auth Context
- Derived State in Forms
- Anti-Patterns

## Form State vs UI State

In this project, use React Hook Form for **form state** and `useState` for **UI state**:

| State Type | Tool | Example |
|------------|------|---------|
| Field values | RHF (`useForm`) | deposit_amount, phone, name |
| Validation errors | RHF (`formState.errors`) | "Phone number is invalid" |
| Submission status | RHF (`formState.isSubmitting`) | Button disabled during save |
| Dirty tracking | RHF (`formState.isDirty`) | "You have unsaved changes" |
| Modal open/close | `useState` | `const [open, setOpen] = useState(false)` |
| Active tab | `useState` | `const [tab, setTab] = useState("general")` |
| Fetched list data | `useState` | `const [barbers, setBarbers] = useState([])` |

NEVER put non-form UI state into RHF. NEVER put field values into `useState` when RHF is managing the form.

## RHF Internal State

RHF tracks more than just values. Access via `form.formState`:

```jsx
const { formState: { errors, isDirty, isSubmitting, isValid, dirtyFields, touchedFields } } = form;

// Unsaved changes warning
{isDirty && (
  <p className="text-sm text-amber-400">You have unsaved changes.</p>
)}

// Disable submit when clean or submitting
<Button type="submit" disabled={!isDirty || isSubmitting}>
  {isSubmitting ? "Saving..." : "Save Settings"}
</Button>
```

### WARNING: Duplicating RHF State in useState

**The Problem:**

```jsx
// BAD - tracking what RHF already tracks
const [loading, setLoading] = useState(false);
const [hasChanges, setHasChanges] = useState(false);

const onSubmit = async (data) => {
  setLoading(true);
  setHasChanges(false);
  // ...
  setLoading(false);
};
```

**Why This Breaks:**
1. `loading` duplicates `isSubmitting` — if the async function throws, `setLoading(false)` in `finally` might not match RHF's state
2. `hasChanges` duplicates `isDirty` — RHF auto-tracks dirty state per field, including after reset
3. Two sources of truth means the "Save" button can be enabled when it shouldn't be

**The Fix:**

```jsx
// GOOD - use RHF's built-in state
const onSubmit = async (data) => {
  await axios.patch(`${API}/shop/policy`, data);
  form.reset(data); // Clears isDirty
  toast.success("Settings saved");
};

<Button disabled={!form.formState.isDirty || form.formState.isSubmitting}>
  {form.formState.isSubmitting ? "Saving..." : "Save"}
</Button>
```

## Connecting to Auth Context

This project uses React Context for auth (see `frontend/src/App.js`). Forms that need auth data should read from context, not from form state:

```jsx
import { useAuth } from "@/App"; // or wherever AuthContext is exported

function ProtectedForm() {
  const { user, token } = useAuth();
  const form = useForm({ resolver: zodResolver(schema), defaultValues });

  const onSubmit = async (data) => {
    // axios interceptors add the token automatically (configured in App.js)
    await axios.patch(`${API}/shop/policy`, data);
  };

  return (
    <Form {...form}>
      <form onSubmit={form.handleSubmit(onSubmit)}>
        <p className="text-sm text-muted-foreground">Logged in as {user.username}</p>
        {/* form fields */}
      </form>
    </Form>
  );
}
```

The auth token is never a form field. The axios interceptor in `App.js` attaches it to every request header automatically.

## Derived State in Forms

Compute derived values during render — NEVER store them in state:

```jsx
// GOOD - computed during render
function PricePreview({ control }) {
  const depositAmount = useWatch({ control, name: "deposit_amount" });
  const taxRate = 0.08;
  const totalWithTax = depositAmount * (1 + taxRate);

  return (
    <p className="text-sm text-muted-foreground font-mono">
      Total with tax: ${totalWithTax.toFixed(2)}
    </p>
  );
}
```

```jsx
// BAD - storing derived value in state
const [totalWithTax, setTotalWithTax] = useState(0);
useEffect(() => {
  setTotalWithTax(form.watch("deposit_amount") * 1.08);
}, [form.watch("deposit_amount")]);
// Creates a render loop: watch triggers re-render, re-render calls watch again
```

## State Scope Decision Tree

When adding new state to a form component:

1. **Is it a field value the user edits?** → RHF field (via `FormField`)
2. **Is it computed from field values?** → Derive during render (or `useWatch`)
3. **Is it a loading/error/dirty flag for the form?** → Use `formState`
4. **Is it UI chrome (modals, tabs, tooltips)?** → `useState`
5. **Is it data fetched from the API to populate dropdowns?** → `useState` + `useEffect`
6. **Is it shared across multiple components?** → React Context (this project avoids Redux/Zustand)

See the **react** skill for Context API patterns and the auth flow.
