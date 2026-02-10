# Forms Reference

## Contents
- Form Patterns in This Codebase
- Controlled Input Pattern
- Form Submission Pattern
- shadcn/ui Form Component
- WARNING: Form Anti-Patterns

## Form Patterns in This Codebase

Two form patterns coexist:

| Pattern | Used In | When |
|---------|---------|------|
| Plain controlled inputs | LoginPage, SettingsPage, SMSConsentPage | Simple forms, few fields |
| React Hook Form + Zod | Available via shadcn `form.jsx` | Complex validation (not yet used in pages) |

See the **react-hook-form** skill for the RHF + Zod pattern.

## Controlled Input Pattern

### Simple Fields (LoginPage.jsx:11-13)

```jsx
const [username, setUsername] = useState("");
const [password, setPassword] = useState("");

<Input
  id="username"
  type="text"
  value={username}
  onChange={(e) => setUsername(e.target.value)}
  required
/>
```

### Object State for Multiple Fields (SettingsPage.jsx:32-38)

```jsx
const [formData, setFormData] = useState({
  deposit_amount: 20,
  deposit_required_hours: 48,
  confirmation_window_hours: 24,
  cancellation_window_hours: 4,
  max_messages_per_day: 4
});

// Update single field with functional setState
<Input
  type="number"
  step="0.01"
  value={formData.deposit_amount}
  onChange={(e) => setFormData(prev => ({
    ...prev,
    deposit_amount: parseFloat(e.target.value)
  }))}
/>
```

**Type conversion is inline:** `parseFloat()` for decimals, `parseInt()` for integers. No external parsing.

### Pre-populating from API (SettingsPage.jsx:44-61)

```jsx
useEffect(() => { fetchShop(); }, []);

const fetchShop = async () => {
  const response = await axios.get(`${API}/shop`);
  setFormData({
    deposit_amount: response.data.deposit_amount,
    deposit_required_hours: response.data.deposit_required_hours,
    // ...
  });
};
```

## Form Submission Pattern

### With Loading State (LoginPage.jsx:27-40)

```jsx
const handleSubmit = async (e) => {
  e.preventDefault();
  setLoading(true);
  try {
    await login(username, password);
    toast.success("Welcome back!");
    navigate(from, { replace: true });
  } catch (error) {
    toast.error(error.response?.data?.detail || "Login failed");
  } finally {
    setLoading(false);
  }
};

<form onSubmit={handleSubmit}>
  {/* inputs */}
  <Button type="submit" disabled={loading}>
    {loading ? "Signing in..." : "Sign In"}
  </Button>
</form>
```

### PATCH Without Form Element (SettingsPage.jsx:63-74)

```jsx
const handleSave = async () => {
  setSaving(true);
  try {
    await axios.patch(`${API}/shop/policy`, formData);
    toast.success("Settings saved successfully");
    fetchShop(); // refetch to sync
  } catch (error) {
    toast.error("Failed to save settings");
  } finally {
    setSaving(false);
  }
};

<Button onClick={handleSave} disabled={saving}>
  <Save className="w-4 h-4 mr-2" />
  {saving ? "Saving..." : "Save Settings"}
</Button>
```

**Note:** SettingsPage uses `onClick` on a Button, not `onSubmit` on a `<form>`. This works because there are no Enter-key submission requirements.

### Reset After Submit (SettingsPage.jsx:76-95)

```jsx
const handleSendTestSMS = async () => {
  if (!testSMS.phone || !testSMS.message) {
    toast.error("Please enter phone number and message");
    return;
  }
  setSendingTest(true);
  try {
    await axios.post(`${API}/sms/send-test`, { to_phone: testSMS.phone, message: testSMS.message });
    toast.success("Test SMS sent!");
    setTestSMS({ phone: "", message: "" }); // clear form
  } catch (error) {
    toast.error(error.response?.data?.detail || "Failed to send test SMS");
  } finally {
    setSendingTest(false);
  }
};
```

## shadcn/ui Form Component

The `form.jsx` component wraps React Hook Form and exists in `src/components/ui/form.jsx`. It provides:
- `FormField` — Controller wrapper
- `FormItem` — Container with unique ID
- `FormLabel` — Label with error styling
- `FormControl` — Slot with aria attributes
- `FormMessage` — Error display

**Currently unused in page components.** If adding forms with complex validation, use this with Zod. See the **react-hook-form** skill.

## Validation

Current validation is minimal:
- HTML5 `required` attribute on inputs
- Manual checks before submit (`if (!testSMS.phone || !testSMS.message)`)
- No Zod schemas in page components (available via dependencies)

## WARNING: Form Anti-Patterns

### WARNING: NaN from Number Inputs

**The Problem:**

```jsx
// BAD — User clears input, gets NaN
onChange={(e) => setFormData(prev => ({
  ...prev,
  amount: parseFloat(e.target.value)
}))}
```

**Why This Breaks:** `parseFloat("")` returns `NaN`. The field becomes uncontrollable.

**The Fix:**

```jsx
onChange={(e) => setFormData(prev => ({
  ...prev,
  amount: e.target.value === "" ? 0 : parseFloat(e.target.value)
}))}
```

**Note:** This codebase has this vulnerability in SettingsPage — the fields use `parseFloat`/`parseInt` without NaN guards.

### WARNING: Missing Form Element for Keyboard Submit

**The Problem:** SettingsPage uses `<Button onClick={handleSave}>` without a `<form>` wrapper. Users cannot press Enter to submit.

**When You Might Be Tempted:** When a form has only number inputs or when the "form" is really a settings panel. Acceptable for settings pages but not for login or data entry forms.