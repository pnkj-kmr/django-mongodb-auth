from rest_framework import serializers
from django.contrib.auth.password_validation import validate_password
from django.core.exceptions import ValidationError as DjangoValidationError
from .models import User
from .jwt_utils import JWTUtils
import re


class UserRegistrationSerializer(serializers.Serializer):
    """Serializer for user registration."""

    email = serializers.EmailField()
    username = serializers.CharField(max_length=150)
    first_name = serializers.CharField(max_length=30)
    last_name = serializers.CharField(max_length=30)
    password = serializers.CharField(write_only=True, min_length=8)
    password_confirm = serializers.CharField(write_only=True)
    phone = serializers.CharField(max_length=20, required=False, allow_blank=True)
    bio = serializers.CharField(required=False, allow_blank=True)

    def validate_email(self, value):
        """Validate email uniqueness."""
        if User.objects.filter(email=value).first():
            raise serializers.ValidationError("User with this email already exists.")
        return value.lower()

    def validate_username(self, value):
        """Validate username uniqueness and format."""
        # Username format validation
        if not re.match(r"^[a-zA-Z0-9_]+$", value):
            raise serializers.ValidationError(
                "Username can only contain letters, numbers, and underscores."
            )

        if User.objects.filter(username=value).first():
            raise serializers.ValidationError("Username already exists.")
        return value

    def validate_password(self, value):
        """Validate password strength."""
        try:
            validate_password(value)
        except DjangoValidationError as e:
            raise serializers.ValidationError(list(e.messages))
        return value

    def validate_phone(self, value):
        """Validate phone number format."""
        if value and value.strip():
            # Simple phone validation (adjust regex as needed)
            phone_pattern = re.compile(r"^\+?[\d\s\-\(\)]+$")
            if not phone_pattern.match(value):
                raise serializers.ValidationError("Invalid phone number format.")
        return value

    def validate(self, attrs):
        """Cross-field validation."""
        if attrs["password"] != attrs["password_confirm"]:
            raise serializers.ValidationError(
                {"password_confirm": "Passwords don't match."}
            )
        return attrs

    def create(self, validated_data):
        """Create new user."""
        validated_data.pop("password_confirm")
        password = validated_data.pop("password")

        user = User(**validated_data)
        user.set_password(password)
        user.save()
        return user


class UserLoginSerializer(serializers.Serializer):
    """Serializer for user login."""

    email = serializers.EmailField()
    password = serializers.CharField(write_only=True)
    remember_me = serializers.BooleanField(default=False, required=False)

    def validate(self, attrs):
        """Validate user credentials."""
        email = attrs.get("email", "").lower()
        password = attrs.get("password")

        if not email or not password:
            raise serializers.ValidationError(
                {"non_field_errors": "Email and password are required."}
            )

        # Check user exists and is active
        try:
            user = User.objects.get(email=email)
        except User.DoesNotExist:
            raise serializers.ValidationError(
                {"non_field_errors": "Invalid email or password."}
            )

        if not user.is_active:
            raise serializers.ValidationError(
                {"non_field_errors": "User account is disabled."}
            )

        if not user.check_password(password):
            raise serializers.ValidationError(
                {"non_field_errors": "Invalid email or password."}
            )

        attrs["user"] = user
        return attrs


class UserSerializer(serializers.Serializer):
    """Serializer for user data display."""

    id = serializers.CharField(read_only=True)
    email = serializers.EmailField(read_only=True)
    username = serializers.CharField(read_only=True)
    first_name = serializers.CharField()
    last_name = serializers.CharField()
    phone = serializers.CharField(allow_blank=True)
    bio = serializers.CharField(allow_blank=True)
    profile_image = serializers.CharField(allow_blank=True)
    date_joined = serializers.DateTimeField(read_only=True)
    last_login = serializers.DateTimeField(read_only=True)
    is_active = serializers.BooleanField(read_only=True)
    full_name = serializers.SerializerMethodField()

    def get_full_name(self, obj):
        """Get user's full name."""
        return obj.get_full_name()


class UserUpdateSerializer(serializers.Serializer):
    """Serializer for updating user profile."""

    username = serializers.CharField(max_length=150, required=False)
    first_name = serializers.CharField(max_length=30, required=False)
    last_name = serializers.CharField(max_length=30, required=False)
    phone = serializers.CharField(max_length=20, required=False, allow_blank=True)
    bio = serializers.CharField(required=False, allow_blank=True)
    profile_image = serializers.CharField(required=False, allow_blank=True)

    def validate_username(self, value):
        """Validate username uniqueness."""
        user = self.context["user"]
        if User.objects.filter(username=value).exclude(id=user.id).first():
            raise serializers.ValidationError("Username already exists.")
        return value

    def validate_profile_image(self, value):
        """Validate profile image URL."""
        if value and value.strip():
            url_pattern = re.compile(
                r"^https?://"
                r"(?:(?:[A-Z0-9](?:[A-Z0-9-]{0,61}[A-Z0-9])?\.)+[A-Z]{2,6}\.?|"
                r"localhost|"
                r"\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3})"
                r"(?::\d+)?"
                r"(?:/?|[/?]\S+)$",
                re.IGNORECASE,
            )

            if not url_pattern.match(value):
                raise serializers.ValidationError("Invalid URL format.")
        return value

    def update(self, instance, validated_data):
        """Update user instance."""
        for attr, value in validated_data.items():
            setattr(instance, attr, value)
        instance.save()
        return instance


class ChangePasswordSerializer(serializers.Serializer):
    """Serializer for changing user password."""

    old_password = serializers.CharField(required=True, write_only=True)
    new_password = serializers.CharField(required=True, write_only=True, min_length=8)
    confirm_password = serializers.CharField(required=True, write_only=True)

    def validate_new_password(self, value):
        """Validate new password strength."""
        try:
            validate_password(value)
        except DjangoValidationError as e:
            raise serializers.ValidationError(list(e.messages))
        return value

    def validate(self, attrs):
        """Validate password change data."""
        if attrs["new_password"] != attrs["confirm_password"]:
            raise serializers.ValidationError(
                {"confirm_password": "New passwords don't match."}
            )
        return attrs


class RefreshTokenSerializer(serializers.Serializer):
    """Serializer for token refresh."""

    refresh = serializers.CharField(required=True)


class LogoutSerializer(serializers.Serializer):
    """Serializer for user logout."""

    refresh = serializers.CharField(required=False)
    logout_all = serializers.BooleanField(default=False, required=False)
