# JWT Auth Patterns

## Contents
- Token Creation and Claims
- FastAPI Auth Dependency Chain
- Frontend Token Lifecycle
- Anti-Patterns

## Token Creation and Claims

Tokens are created in `backend/server.py:81-85` using PyJWT's `jwt.encode()`:

```python
def create_access_token(data: dict) -> str:
    to_encode = data.copy()
    expire = datetime.now(timezone.utc) + timedelta(hours=ACCESS_TOKEN_EXPIRE_HOURS)
    to_encode.update({"exp": expire})
    return jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)
```

Key decisions:
- **HS256** symmetric signing — single-server deployment, no need for RS256
- **24-hour expiry** — no refresh token mechanism exists
- **Claims are flat** — `sub`, `username`, `shop_id`, `exp` only
- Uses `datetime.now(timezone.utc)` — NEVER use `datetime.utcnow()` (deprecated, returns naive datetime)

### WARNING: Adding Sensitive Data to Claims

**The Problem:**

```python
# BAD - Token payload is base64, not encrypted
token = create_access_token({
    "sub": admin["id"],
    "email": admin["email"],
    "password_hash": admin["password_hash"],  # Exposed!
    "shop_id": admin["shop_id"]
})
```

**Why This Breaks:**
1. JWT payload is base64-encoded, readable by anyone with the token
2. Password hashes, PII, or internal IDs leak to the client
3. Tokens stored in localStorage are accessible to any JS on the page

**The Fix:**

```python
# GOOD - Minimal claims, look up details server-side
token = create_access_token({
    "sub": admin["id"],
    "username": admin["username"],
    "shop_id": admin["shop_id"]
})
```

## FastAPI Auth Dependency Chain

The project uses a two-level dependency chain:

```python
# Level 1: Extract and verify token (server.py:98-108)
async def get_current_user(authorization: Optional[str] = Header(None)) -> dict:
    if not authorization or not authorization.startswith("Bearer "):
        raise HTTPException(status_code=401, detail="Not authenticated")
    token = authorization.split(" ")[1]
    payload = verify_token(token)
    if not payload:
        raise HTTPException(status_code=401, detail="Invalid or expired token")
    return payload

# Level 2: Resolve shop from user claims (server.py:111-116)
async def get_shop(user: dict = Depends(get_current_user)) -> Shop:
    shop_data = await db.shops.find_one({"id": user.get("shop_id")}, {"_id": 0})
    if not shop_data:
        raise HTTPException(status_code=404, detail="Shop not found")
    return Shop(**shop_data)
```

Use `Depends(get_current_user)` when you need user claims. Use `Depends(get_shop)` when you need the shop object — it chains through `get_current_user` automatically.

### WARNING: Bypassing the Dependency Chain

**The Problem:**

```python
# BAD - Manually parsing auth header
@api_router.get("/my-endpoint")
async def my_endpoint(request: Request):
    token = request.headers.get("Authorization", "").replace("Bearer ", "")
    payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
```

**Why This Breaks:**
1. Duplicates validation logic — misses edge cases handled by `get_current_user`
2. No consistent error response format
3. If auth logic changes, this endpoint breaks silently

**The Fix:**

```python
# GOOD - Use the dependency
@api_router.get("/my-endpoint")
async def my_endpoint(user: dict = Depends(get_current_user)):
    shop_id = user.get("shop_id")
```

## Frontend Token Lifecycle

### Storage and Attachment

Token stored in `localStorage` under key `"token"`. The axios request interceptor auto-attaches it:

```javascript
// App.js:25-31 — Runs on every request
axios.interceptors.request.use((config) => {
  const token = localStorage.getItem("token");
  if (token) {
    config.headers.Authorization = `Bearer ${token}`;
  }
  return config;
});
```

### Auto-Logout on 401

```javascript
// App.js:33-42 — Any 401 clears token and redirects
axios.interceptors.response.use(
  (response) => response,
  (error) => {
    if (error.response?.status === 401) {
      localStorage.removeItem("token");
      window.location.href = "/login";
    }
    return Promise.reject(error);
  }
);
```

### WARNING: Reading Token Before Auth Check Completes

**The Problem:**

```javascript
// BAD - Component renders before checkAuth() resolves
const MyComponent = () => {
  const { user } = useAuth();
  // user is null during initial load — causes crashes
  return <div>{user.username}</div>;
};
```

**Why This Breaks:**
1. `AuthProvider.checkAuth()` is async — `user` starts as `null`
2. Components accessing `user` properties crash before auth resolves

**The Fix:**

```javascript
// GOOD - Guard with ProtectedRoute (handles loading state)
<ProtectedRoute>
  <MyComponent />
</ProtectedRoute>

// Or check loading state explicitly
const { user, loading } = useAuth();
if (loading) return <Spinner />;
```

## Password Hashing

Passwords are hashed with bcrypt via passlib (`server.py:59`):

```python
pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")

# Seed: hash the password
"password_hash": pwd_context.hash(admin_password)

# Login: verify against hash
pwd_context.verify(request.password, admin["password_hash"])
```

NEVER store plaintext passwords. NEVER compare passwords with `==`. Always use `pwd_context.verify()`.