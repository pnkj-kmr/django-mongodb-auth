from django.core.cache import cache
from .models import UserActivity
import json


class ActivityTracker:
    """Utility class for tracking user activities."""

    @staticmethod
    def track_activity(
        user_id, action, target_type, target_id, metadata=None, request=None
    ):
        """Track user activity."""
        try:
            activity_data = {
                "user_id": str(user_id),
                "action": action,
                "target_type": target_type,
                "target_id": str(target_id),
                "metadata": json.dumps(metadata or {}),
            }

            if request:
                activity_data["ip_address"] = get_client_ip(request)
                activity_data["user_agent"] = request.META.get("HTTP_USER_AGENT", "")[
                    :200
                ]

            activity = UserActivity(**activity_data)
            activity.save()

            return activity
        except Exception as e:
            # Log error but don't fail the main operation
            import logging

            logger = logging.getLogger("api")
            logger.error(f"Failed to track activity: {e}")
            return None


def get_client_ip(request):
    """Get client IP address from request."""
    x_forwarded_for = request.META.get("HTTP_X_FORWARDED_FOR")
    if x_forwarded_for:
        ip = x_forwarded_for.split(",")[0]
    else:
        ip = request.META.get("REMOTE_ADDR")
    return ip


def generate_slug(text):
    """Generate URL-friendly slug from text."""
    import re

    # Convert to lowercase and replace spaces with hyphens
    slug = re.sub(r"[^\w\s-]", "", text.lower())
    slug = re.sub(r"[\s_-]+", "-", slug)
    slug = slug.strip("-")
    return slug


def cache_user_stats(user_id):
    """Cache user statistics."""
    from .models import Post, Comment

    try:
        stats = {
            "post_count": Post.objects.filter(
                author_id=user_id, status="published"
            ).count(),
            "draft_count": Post.objects.filter(
                author_id=user_id, status="draft"
            ).count(),
            "comment_count": Comment.objects.filter(
                author_id=user_id, is_approved=True
            ).count(),
            "total_views": sum(
                post.view_count for post in Post.objects.filter(author_id=user_id)
            ),
        }

        cache.set(f"user_stats:{user_id}", stats, timeout=3600)  # Cache for 1 hour
        return stats
    except Exception:
        return {}


def get_cached_user_stats(user_id):
    """Get cached user statistics."""
    stats = cache.get(f"user_stats:{user_id}")
    if stats is None:
        stats = cache_user_stats(user_id)
    return stats
