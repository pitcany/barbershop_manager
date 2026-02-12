"""
Conftest for unit tests.
Sets required environment variables before deps.py is imported.
"""
import os

# deps.py reads these at module level to create the Motor client.
# Provide defaults so imports don't crash in a test-only environment.
os.environ.setdefault("MONGO_URL", "mongodb://localhost:27017")
os.environ.setdefault("DB_NAME", "barbershop_test")
os.environ.setdefault("JWT_SECRET", "test-secret-key-for-unit-tests")
