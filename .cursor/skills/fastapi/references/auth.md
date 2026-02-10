# Auth Reference

## Contents
- JWT Token Flow
- Dependency Chain
- Token Creation and Verification
- Protecting Routes
- Public vs Authenticated vs Webhook Routes
- Anti-Patterns

## JWT Token Flow

```
Client sends POST /api/auth/login {username, password}
  → server verifies bcrypt hash
  → server creates JWT with {sub, username, shop_id, exp}
  → returns {access_token, token_type: "bearer"}

Client includes header: Authorization: Bearer <token>
  → get_current_user extracts and verifies token
  → get_shop loads Shop from DB using shop_id from token
  → route handler receives Shop object
```

See the **jwt** skill for token standards and security.

## Dependency Chain

```python
# 1. Extract + verify JWT from Authorization header
async def get_current_user(authorization: Optional[str] = Header(None)) -> dict:
    if not authorization or not authorization.startswith("Bearer "):
        raise HTTPException(status_code=401, detail="Not authenticated")
    token = authorization.split(" ")[1]
    payload = verify_token(token)
    if not payload:
        raise HTTPException(status_code=401, detail="Invalid or expired token")
    return payload

# 2. Load shop from token's shop_id claim
async def get_shop(user: dict = Depends(get_current_user)) -> Shop:
    shop_data = await db.shops.find_one({"id": user.get("shop_id")}, {"_id": 0})
    if not shop_data:
        raise HTTPException(status_code=404, detail="Shop not found")
    return Shop(**shop_data)
```

Most routes use `Depends(get_shop)` which chains through `get_current_user`:

```python
@api_router.get("/appointments")
async def list_appointments(shop: Shop = Depends(get_shop)):
    # shop is guaranteed valid here
    ...
```

To access the raw token payload (e.g., for user ID), use `Depends(get_current_user)`:

```python
@api_router.get("/auth/me")
async def get_me(user: dict = Depends(get_current_user)):
    return {"id": user.get("sub"), "username": user.get("username")}
```

## Token Creation and Verification

```python
SECRET_KEY = os.environ.get('JWT_SECRET', 'barbershop-autopilot-secret-key-change-in-production')
ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_HOURS = 24

def create_access_token(data: dict) -> str:
    to_encode = data.copy()
    expire = datetime.now(timezone.utc) + timedelta(hours=ACCESS_TOKEN_EXPIRE_HOURS)
    to_encode.update({"exp": expire})
    return jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)

def verify_token(token: str) -> Optional[dict]:
    try:
        return jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
    except jwt.ExpiredSignatureError:
        return None
    except jwt.InvalidTokenError:
        return None
```

**Token payload:**
```json
{
  "sub": "admin_1",
  "username": "admin",
  "shop_id": "demo_shop",
  "exp": 1234567890
}
```

## Protecting Routes

### Authenticated (Most Routes)

```python
@api_router.get("/barbers")
async def list_barbers(shop: Shop = Depends(get_shop)):
    # JWT required, shop loaded automatically
    ...
```

### Public (No Auth)

```python
@api_router.post("/public/sms-consent")
async def submit_sms_consent(request: SMSConsentRequest):
    # No Depends — anyone can submit consent
    ...
```

### Webhooks (Signature Auth)

```python
@api_router.post("/webhooks/stripe")
async def stripe_webhook(request: Request):
    # No JWT — authenticated via Stripe-Signature header
    body = await request.body()
    signature = request.headers.get("Stripe-Signature", "")
    result = await payment.handle_webhook(body, signature)
```

## Password Handling

```python
from passlib.context import CryptContext
pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")

# Hash on user creation
password_hash = pwd_context.hash(admin_password)

# Verify on login
if not pwd_context.verify(request.password, admin["password_hash"]):
    raise HTTPException(status_code=401, detail="Invalid credentials")
```

## Anti-Patterns

### WARNING: Hardcoded JWT Secret in Production

The default secret is `barbershop-autopilot-secret-key-change-in-production`. In production, `JWT_SECRET` env var MUST be set to a strong random value. The current default is acceptable for local dev only.

### WARNING: No Token Refresh

Tokens expire after 24 hours with no refresh mechanism. The frontend must re-authenticate. If you add refresh tokens, store them in a separate collection and validate on use.

### WARNING: Accessing `user` Fields Without `.get()`

Token payloads should always be accessed with `.get()` for safety:

```python
# GOOD
user.get("shop_id")
user.get("sub")

# BAD — KeyError if token is malformed
user["shop_id"]
```