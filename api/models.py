from mongoengine import (
    Document,
    StringField,
    EmailField,
    BooleanField,
    DateTimeField,
    ListField,
    ReferenceField,
    IntField,
)
from datetime import datetime
import uuid


class Category(Document):
    """Category model for organizing posts."""

    id = StringField(primary_key=True, default=lambda: str(uuid.uuid4()))
    name = StringField(required=True, unique=True, max_length=100)
    slug = StringField(required=True, unique=True, max_length=100)
    description = StringField(default="")
    color = StringField(default="#007bff")  # Hex color for UI
    is_active = BooleanField(default=True)
    created_at = DateTimeField(default=datetime.utcnow)

    meta = {"collection": "categories", "indexes": ["name", "slug", "is_active"]}

    def __str__(self):
        return self.name


class Post(Document):
    """Post model with full features."""

    id = StringField(primary_key=True, default=lambda: str(uuid.uuid4()))
    title = StringField(required=True, max_length=200)
    slug = StringField(required=True, unique=True, max_length=200)
    content = StringField(required=True)
    excerpt = StringField(max_length=300, default="")

    # Relationships
    author_id = StringField(required=True)  # Reference to User
    category = ReferenceField(Category)

    # Media
    featured_image = StringField(default="")
    images = ListField(StringField(), default=list)

    # Metadata
    tags = ListField(StringField(), default=list)
    meta_description = StringField(max_length=160, default="")

    # Status
    status = StringField(choices=["draft", "published", "archived"], default="draft")
    is_featured = BooleanField(default=False)

    # Stats
    view_count = IntField(default=0)
    like_count = IntField(default=0)
    comment_count = IntField(default=0)

    # Timestamps
    created_at = DateTimeField(default=datetime.utcnow)
    updated_at = DateTimeField(default=datetime.utcnow)
    published_at = DateTimeField()

    meta = {
        "collection": "posts",
        "indexes": [
            "author_id",
            "status",
            "slug",
            "-created_at",
            "-published_at",
            "is_featured",
            "tags",
        ],
    }

    def save(self, *args, **kwargs):
        """Override save to update timestamp."""
        self.updated_at = datetime.utcnow()

        # Set published_at when status changes to published
        if self.status == "published" and not self.published_at:
            self.published_at = datetime.utcnow()

        super().save(*args, **kwargs)

    def __str__(self):
        return self.title


class Comment(Document):
    """Comment model for posts."""

    id = StringField(primary_key=True, default=lambda: str(uuid.uuid4()))
    content = StringField(required=True)

    # Relationships
    post = ReferenceField(Post, required=True)
    author_id = StringField(required=True)  # Reference to User
    parent = ReferenceField("self")  # For nested comments

    # Status
    is_approved = BooleanField(default=True)
    is_edited = BooleanField(default=False)

    # Timestamps
    created_at = DateTimeField(default=datetime.utcnow)
    updated_at = DateTimeField(default=datetime.utcnow)

    meta = {
        "collection": "comments",
        "indexes": ["post", "author_id", "-created_at", "is_approved"],
    }

    def save(self, *args, **kwargs):
        """Override save to update timestamp."""
        self.updated_at = datetime.utcnow()
        super().save(*args, **kwargs)

    def __str__(self):
        return f"Comment by {self.author_id} on {self.post.title}"


class UserActivity(Document):
    """Track user activities for analytics."""

    id = StringField(primary_key=True, default=lambda: str(uuid.uuid4()))
    user_id = StringField(required=True)
    action = StringField(required=True)  # 'view', 'like', 'comment', 'create', etc.
    target_type = StringField(required=True)  # 'post', 'comment', 'user', etc.
    target_id = StringField(required=True)

    # Additional data
    metadata = StringField(default="{}")  # JSON string for extra data
    ip_address = StringField(default="")
    user_agent = StringField(default="")

    # Timestamp
    created_at = DateTimeField(default=datetime.utcnow)

    meta = {
        "collection": "user_activities",
        "indexes": ["user_id", "action", "target_type", "-created_at"],
    }

    def __str__(self):
        return f"{self.user_id} {self.action} {self.target_type}:{self.target_id}"
