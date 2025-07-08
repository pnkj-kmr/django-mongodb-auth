from mongoengine import (
    Document,
    StringField,
    EmailField,
    BooleanField,
    DateTimeField,
    URLField,
    ListField,
)
from django.contrib.auth.hashers import make_password, check_password
from django.utils import timezone
from datetime import datetime
import uuid


class User(Document):
    """
    MongoEngine User model for MongoDB storage.
    This replaces Django's User model for our API.
    """

    # Primary identification
    id = StringField(primary_key=True, default=lambda: str(uuid.uuid4()))
    email = EmailField(required=True, unique=True)
    username = StringField(required=True, unique=True, max_length=150)

    # Password (hashed)
    password = StringField(required=True)

    # Personal information
    first_name = StringField(max_length=30, default="")
    last_name = StringField(max_length=30, default="")
    phone = StringField(max_length=20, default="")
    bio = StringField(default="")
    profile_image = StringField(default="")

    # Account status
    is_active = BooleanField(default=True)
    is_staff = BooleanField(default=False)
    is_superuser = BooleanField(default=False)

    # Timestamps
    date_joined = DateTimeField(default=datetime.utcnow)
    last_login = DateTimeField()
    updated_at = DateTimeField(default=datetime.utcnow)

    # Additional fields for JWT
    refresh_tokens = ListField(
        StringField(), default=list
    )  # Store active refresh tokens

    meta = {
        "collection": "users",
        "indexes": ["email", "username", "-date_joined", "is_active"],
    }

    def set_password(self, raw_password):
        """Set password with Django's password hashing."""
        self.password = make_password(raw_password)

    def check_password(self, raw_password):
        """Check password using Django's password verification."""
        return check_password(raw_password, self.password)

    def save(self, *args, **kwargs):
        """Override save to update timestamp."""
        self.updated_at = datetime.utcnow()
        super().save(*args, **kwargs)

    def get_full_name(self):
        """Return full name."""
        return f"{self.first_name} {self.last_name}".strip()

    def get_short_name(self):
        """Return short name."""
        return self.first_name or self.username

    def __str__(self):
        return self.email

    def __repr__(self):
        return f"<User: {self.email}>"

    # Authentication properties for Django compatibility
    @property
    def is_authenticated(self):
        """Always return True for authenticated users."""
        return True

    @property
    def is_anonymous(self):
        """Always return False for authenticated users."""
        return False

    # Helper methods
    def add_refresh_token(self, token_jti):
        """Add refresh token JTI to user's active tokens."""
        if token_jti not in self.refresh_tokens:
            self.refresh_tokens.append(token_jti)
            # Keep only last 5 refresh tokens
            if len(self.refresh_tokens) > 5:
                self.refresh_tokens = self.refresh_tokens[-5:]
            self.save()

    def remove_refresh_token(self, token_jti):
        """Remove refresh token JTI from user's active tokens."""
        if token_jti in self.refresh_tokens:
            self.refresh_tokens.remove(token_jti)
            self.save()

    def clear_refresh_tokens(self):
        """Clear all refresh tokens (logout from all devices)."""
        self.refresh_tokens = []
        self.save()
