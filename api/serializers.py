from rest_framework import serializers
from accounts.models import User
from .models import Post, Category, Comment, UserActivity
import re
import json


class CategorySerializer(serializers.Serializer):
    """Serializer for Category model."""

    id = serializers.CharField(read_only=True)
    name = serializers.CharField(max_length=100)
    slug = serializers.CharField(max_length=100)
    description = serializers.CharField(allow_blank=True)
    color = serializers.CharField(max_length=7, default="#007bff")
    is_active = serializers.BooleanField(default=True)
    created_at = serializers.DateTimeField(read_only=True)
    post_count = serializers.SerializerMethodField()

    def get_post_count(self, obj):
        """Get number of published posts in this category."""
        return Post.objects.filter(category=obj, status="published").count()

    def validate_slug(self, value):
        """Validate slug format and uniqueness."""
        if not re.match(r"^[a-z0-9-]+$", value):
            raise serializers.ValidationError(
                "Slug can only contain lowercase letters, numbers, and hyphens."
            )

        # Check uniqueness (exclude current instance if updating)
        existing = Category.objects.filter(slug=value).first()
        if existing and (
            not hasattr(self, "instance") or existing.id != self.instance.id
        ):
            raise serializers.ValidationError("Category with this slug already exists.")

        return value

    def validate_color(self, value):
        """Validate hex color format."""
        if not re.match(r"^#[0-9a-fA-F]{6}$", value):
            raise serializers.ValidationError(
                "Color must be a valid hex color (e.g., #007bff)."
            )
        return value


class AuthorSerializer(serializers.Serializer):
    """Serializer for author information."""

    id = serializers.CharField()
    username = serializers.CharField()
    first_name = serializers.CharField()
    last_name = serializers.CharField()
    profile_image = serializers.CharField()
    full_name = serializers.SerializerMethodField()

    def get_full_name(self, obj):
        """Get author's full name."""
        if hasattr(obj, "get_full_name"):
            return obj.get_full_name()
        return f"{obj.first_name} {obj.last_name}".strip()


class PostSerializer(serializers.Serializer):
    """Serializer for Post model."""

    id = serializers.CharField(read_only=True)
    title = serializers.CharField(max_length=200)
    slug = serializers.CharField(max_length=200)
    content = serializers.CharField()
    excerpt = serializers.CharField(max_length=300, allow_blank=True)

    # Relationships
    category_id = serializers.CharField(
        write_only=True, required=False, allow_null=True
    )
    category = CategorySerializer(read_only=True)
    author = serializers.SerializerMethodField()

    # Media
    featured_image = serializers.CharField(allow_blank=True)
    images = serializers.ListField(child=serializers.CharField(), required=False)

    # Metadata
    tags = serializers.ListField(child=serializers.CharField(), required=False)
    meta_description = serializers.CharField(max_length=160, allow_blank=True)

    # Status
    status = serializers.ChoiceField(
        choices=["draft", "published", "archived"], default="draft"
    )
    is_featured = serializers.BooleanField(default=False)

    # Stats (read-only)
    view_count = serializers.IntegerField(read_only=True)
    like_count = serializers.IntegerField(read_only=True)
    comment_count = serializers.IntegerField(read_only=True)

    # Timestamps
    created_at = serializers.DateTimeField(read_only=True)
    updated_at = serializers.DateTimeField(read_only=True)
    published_at = serializers.DateTimeField(read_only=True)

    def get_author(self, obj):
        """Get author information."""
        try:
            author = User.objects.get(id=obj.author_id)
            return AuthorSerializer(author).data
        except User.DoesNotExist:
            return None

    def validate_slug(self, value):
        """Validate slug format and uniqueness."""
        if not re.match(r"^[a-z0-9-]+$", value):
            raise serializers.ValidationError(
                "Slug can only contain lowercase letters, numbers, and hyphens."
            )

        # Check uniqueness (exclude current instance if updating)
        existing = Post.objects.filter(slug=value).first()
        if existing and (
            not hasattr(self, "instance") or existing.id != self.instance.id
        ):
            raise serializers.ValidationError("Post with this slug already exists.")

        return value

    def validate_category_id(self, value):
        """Validate category exists."""
        if value:
            try:
                Category.objects.get(id=value, is_active=True)
            except Category.DoesNotExist:
                raise serializers.ValidationError("Category not found or inactive.")
        return value

    def validate_tags(self, value):
        """Validate and clean tags."""
        if value:
            # Clean and deduplicate tags
            cleaned_tags = []
            for tag in value:
                clean_tag = tag.strip().lower()
                if clean_tag and clean_tag not in cleaned_tags:
                    cleaned_tags.append(clean_tag)
            return cleaned_tags[:10]  # Limit to 10 tags
        return []


class PostCreateSerializer(PostSerializer):
    """Serializer for creating posts."""

    def create(self, validated_data):
        """Create new post."""
        category_id = validated_data.pop("category_id", None)

        post = Post(**validated_data)

        if category_id:
            post.category = Category.objects.get(id=category_id)

        post.save()
        return post


class PostUpdateSerializer(PostSerializer):
    """Serializer for updating posts."""

    def update(self, instance, validated_data):
        """Update existing post."""
        category_id = validated_data.pop("category_id", None)

        # Update fields
        for attr, value in validated_data.items():
            setattr(instance, attr, value)

        # Update category if provided
        if category_id:
            instance.category = Category.objects.get(id=category_id)
        elif category_id is None:  # Explicitly remove category
            instance.category = None

        instance.save()
        return instance


class CommentSerializer(serializers.Serializer):
    """Serializer for Comment model."""

    id = serializers.CharField(read_only=True)
    content = serializers.CharField()

    # Relationships
    post_id = serializers.CharField(write_only=True)
    parent_id = serializers.CharField(write_only=True, required=False, allow_null=True)
    author = serializers.SerializerMethodField()

    # Status
    is_approved = serializers.BooleanField(default=True)
    is_edited = serializers.BooleanField(read_only=True)

    # Timestamps
    created_at = serializers.DateTimeField(read_only=True)
    updated_at = serializers.DateTimeField(read_only=True)

    # Nested data
    replies = serializers.SerializerMethodField()
    reply_count = serializers.SerializerMethodField()

    def get_author(self, obj):
        """Get author information."""
        try:
            author = User.objects.get(id=obj.author_id)
            return AuthorSerializer(author).data
        except User.DoesNotExist:
            return None

    def get_replies(self, obj):
        """Get comment replies (only direct children)."""
        replies = Comment.objects.filter(parent=obj, is_approved=True).order_by(
            "created_at"
        )
        return CommentSerializer(replies, many=True, context=self.context).data

    def get_reply_count(self, obj):
        """Get total reply count."""
        return Comment.objects.filter(parent=obj, is_approved=True).count()

    def validate_post_id(self, value):
        """Validate post exists."""
        try:
            Post.objects.get(id=value)
        except Post.DoesNotExist:
            raise serializers.ValidationError("Post not found.")
        return value

    def validate_parent_id(self, value):
        """Validate parent comment exists."""
        if value:
            try:
                Comment.objects.get(id=value)
            except Comment.DoesNotExist:
                raise serializers.ValidationError("Parent comment not found.")
        return value


class UserActivitySerializer(serializers.Serializer):
    """Serializer for UserActivity model."""

    id = serializers.CharField(read_only=True)
    action = serializers.CharField()
    target_type = serializers.CharField()
    target_id = serializers.CharField()
    metadata = serializers.JSONField(default=dict)
    created_at = serializers.DateTimeField(read_only=True)
