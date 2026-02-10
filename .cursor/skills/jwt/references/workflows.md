# JWT Auth Workflows

## Contents
- Adding Auth to a New Endpoint
- Adding a New Protected Frontend Page
- Testing Auth Manually
- Debugging 401 Errors
- Production Security Checklist

## Adding Auth to a New Endpoint

1. Add the route in `backend/server.py` under the appropriate section
2. Use `Depends(get_current_user)` or `Depends(get_shop)` as a parameter

```python
# For user-scoped data
@api_router.get("/my-resource")
async def get_my_resource(user: dict = Depends(get_current_user)):
    shop_id = user.get("shop_id")
    items = await db.my_collection.find(
        {"shop_id": shop_id}, {"_id": 0}
    ).to_list(100)
    return items

# For shop-scoped data (auto-chains through get_current_user)
@api_router.patch("/my-resource/{id}")
async def update_my_resource(id: str, shop: Shop = Depends(get_shop)):
    # shop is already validated
    pass
```

3. No frontend changes needed — axios interceptor attaches the token automatically

Copy this checklist and track progress:
- [ ] Add endpoint in `backend/server.py`
- [ ] Use `Depends(get_current_user)` or `Depends(get_shop)`
- [ ] Filter queries by `shop_id` from token claims
- [ ] Test with valid token (should return 200)
- [ ] Test without token (should return 401)

## Adding a New Protected Frontend Page

1. Create the page component in `frontend/src/pages/`
2. Wrap with `ProtectedRoute` in `App.js`
3. Use `useAuth()` to access user data

```javascript
// frontend/src/pages/MyPage.jsx
import { useAuth } from "../App";
import axios from "axios";
import { API } from "../App";

export default function MyPage() {
  const { user } = useAuth();
  
  const fetchData = async () => {
    // Token attached automatically by interceptor
    const response = await axios.get(`${API}/my-resource`);
    return response.data;
  };
  // ...
}
```

```javascript
// In App.js Routes
<Route path="/my-page" element={
  <ProtectedRoute>
    <MyPage />
  </ProtectedRoute>
} />
```

Copy this checklist and track progress:
- [ ] Create page component in `frontend/src/pages/MyPage.jsx`
- [ ] Add `<Route>` wrapped in `<ProtectedRoute>` in `App.js`
- [ ] Use `useAuth()` for user info, `axios` for API calls
- [ ] Add navigation link in `frontend/src/components/layout/Layout.jsx`
- [ ] Verify redirect to `/login` when unauthenticated

## Testing Auth Manually

The project includes a test suite in `backend_test.py` that tests the full auth flow:

```bash
# Start the backend
cd backend && python -m uvicorn server:app --reload --port 8001

# Run the test suite (includes auth tests)
cd .. && python backend_test.py
```

To test manually with curl:

```bash
# Login and get token
TOKEN=$(curl -s -X POST http://localhost:8001/api/auth/login \
  -H "Content-Type: application/json" \
  -d '{"username":"admin","password":"admin123"}' | python -c "import sys,json;print(json.load(sys.stdin)['access_token'])")

# Use token on protected endpoint
curl -H "Authorization: Bearer $TOKEN" http://localhost:8001/api/auth/me

# Test without token (expect 401)
curl http://localhost:8001/api/appointments
```

## Debugging 401 Errors

Common causes and fixes:

| Symptom | Cause | Fix |
|---------|-------|-----|
| 401 on every request | Token expired (24h) | Re-login. Check server clock drift. |
| 401 after deploy | `JWT_SECRET` changed | All existing tokens are invalidated. Users must re-login. |
| 401 on frontend only | Interceptor not running | Verify `axios.interceptors` registered before any API call |
| 401 with valid token | `algorithms` mismatch | `verify_token` uses `algorithms=[ALGORITHM]` (plural list) |
| Redirect loop to `/login` | `checkAuth()` failing | Check browser console for network errors to `/auth/me` |

Debugging flow:

1. Check browser DevTools Network tab — is `Authorization: Bearer <token>` present?
2. Copy the token, decode at jwt.io — check `exp` claim vs current UTC time
3. Check backend logs — `verify_token` returns `None` silently, add logging if needed
4. Verify `JWT_SECRET` env var matches between token creation and verification

```python
# Temporary debug: add to verify_token() in server.py
def verify_token(token: str) -> Optional[dict]:
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        return payload
    except jwt.ExpiredSignatureError:
        logger.warning("Token expired")
        return None
    except jwt.InvalidTokenError as e:
        logger.warning(f"Invalid token: {e}")
        return None
```

1. Add debug logging to `verify_token()`
2. Reproduce the 401
3. Check server logs for the specific error
4. If `ExpiredSignatureError` — token needs refresh or re-login
5. If `InvalidSignatureError` — secret key mismatch
6. Remove debug logging when done

## Production Security Checklist

Copy this checklist and track progress:
- [ ] Set `JWT_SECRET` to a cryptographically random value (32+ bytes): `python -c "import secrets; print(secrets.token_hex(32))"`
- [ ] Set `ADMIN_PASSWORD` to a strong password (not `admin123`)
- [ ] Set `CORS_ORIGINS` to specific frontend domain (not `*`)
- [ ] Confirm HTTPS is enforced (tokens in transit are plaintext over HTTP)
- [ ] Consider reducing `ACCESS_TOKEN_EXPIRE_HOURS` from 24 to 1-4 hours
- [ ] Add refresh token mechanism if reducing expiry (not currently implemented)
- [ ] Audit `localStorage` usage — vulnerable to XSS; consider `httpOnly` cookies for high-security needs

### WARNING: Missing Refresh Token Mechanism

This project has no refresh tokens. The 24-hour access token acts as both access and session token. This means:
- Users are forcibly logged out every 24 hours
- No way to revoke a compromised token before expiry
- Reducing token expiry to improve security degrades UX without a refresh flow

For production with multiple users, consider adding a `/auth/refresh` endpoint that issues short-lived access tokens (15-30 min) paired with a longer-lived refresh token stored in an `httpOnly` cookie. See the **fastapi** skill for endpoint patterns.