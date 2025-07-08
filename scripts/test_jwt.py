from accounts.models import User
from accounts.jwt_utils import JWTUtils

# Create a test user
user = User(
    email="test@example.com",
    username="testuser",
    first_name="Test",
    last_name="User",
)
user.set_password("password123")
user.save()

# Generate tokens
tokens = JWTUtils.generate_tokens(user)
print("Access Token:", tokens["access"])
print("Refresh Token:", tokens["refresh"])

# Test token validation
payload = JWTUtils.decode_token(tokens["access"])
print("Token Payload:", payload)
