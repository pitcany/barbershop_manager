---
name: jwt
description: |
  Implements JWT token generation, validation, and bearer auth for the Barbershop Autopilot system using PyJWT + bcrypt on the backend and localStorage + axios interceptors on the frontend.
  Use when: adding auth endpoints, modifying token claims, changing expiry, adding protected routes, updating login flow, or debugging 401 errors.
allowed-tools: Read, Edit, Write, Glob, Grep, Bash
---

# JWT Auth

This project uses PyJWT 2.11 with HS256 signing, bcrypt password hashing via passlib, and a React Context + axios interceptor pattern on the frontend. All auth logic lives in two files: `backend/server.py` (lines 54-151) and `frontend/src/App.js` (lines 17-113).

## Key Files

| File | Lines | What |
|------|-------|------|
| `backend/server.py` | 54-108 | `SECRET_KEY`, `create_access_token()`, `verify_token()`, `get_current_user()` |
| `backend/server.py` | 121-151 | `/auth/login`, `/auth/me` endpoints |
| `backend/models.py` | 309-316 | `LoginRequest`, `TokenResponse` Pydantic models |
| `frontend/src/App.js` | 24-42 | Axios interceptors (attach token, handle 401) |
| `frontend/src/App.js` | 65-113 | `AuthProvider` with `login()`, `logout()`, `checkAuth()` |
| `frontend/src/pages/LoginPage.jsx` | — | Login form using `useAuth().login()` |

## Token Structure

```python
# Claims payload (backend/server.py:135-138)
{
    "sub": admin["id"],        # "admin_1"
    "username": admin["username"],  # "admin"
    "shop_id": admin["shop_id"],    # "demo_shop"
    "exp": <utc_now + 24h>
}
```

## Quick Patterns

### Protect a new endpoint

```python
@api_router.get("/my-endpoint")
async def my_endpoint(user: dict = Depends(get_current_user)):
    shop_id = user.get("shop_id")
    # user dict contains sub, username, shop_id, exp
```

### Get the shop object for the current user

```python
@api_router.get("/my-endpoint")
async def my_endpoint(shop: Shop = Depends(get_shop)):
    # shop is a validated Pydantic model
```

### Access token on the frontend

```javascript
// Token is auto-attached by axios interceptor (App.js:25-31)
// Just call the API — no manual header needed
const response = await axios.get(`${API}/appointments`);

// To read the current user:
const { user } = useAuth();  // { id, username, shop_id }
```

## Configuration

| Env Var | Default | Purpose |
|---------|---------|---------|
| `JWT_SECRET` | `barbershop-autopilot-secret-key-change-in-production` | HS256 signing key |
| `ADMIN_PASSWORD` | `admin123` | Seed password (bcrypt hashed at startup) |

**WARNING:** The default `JWT_SECRET` is hardcoded. In production, set a cryptographically random `JWT_SECRET` environment variable (32+ bytes).

## Anti-Patterns

See [patterns](references/patterns.md) for detailed DO/DON'T pairs.

## See Also

- [patterns](references/patterns.md) — Token handling, auth dependency, common mistakes
- [workflows](references/workflows.md) — Adding auth to new features, testing auth, debugging 401s

## Related Skills

- See the **fastapi** skill for endpoint patterns, `Depends()`, and middleware
- See the **react** skill for `AuthContext`, `ProtectedRoute`, and `useAuth()` hook
- See the **python** skill for async patterns and Pydantic model conventions
- See the **axios** skill for interceptor setup and API call patterns