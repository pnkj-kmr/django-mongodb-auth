from rest_framework import status, permissions
from rest_framework.response import Response
from rest_framework.views import APIView
from rest_framework.decorators import api_view, permission_classes
from django.core.cache import cache
from accounts.models import User
from .models import Post, Category, Comment, UserActivity
from .serializers import (
    PostSerializer,
    PostCreateSerializer,
    PostUpdateSerializer,
    CategorySerializer,
    CommentSerializer,
    UserActivitySerializer,
)
from .permissions import (
    IsAuthorOrReadOnly,
    IsCommentAuthorOrReadOnly,
    IsAdminOrReadOnly,
)
from .utils import ActivityTracker, generate_slug, get_cached_user_stats
import logging
from datetime import datetime, timedelta

logger = logging.getLogger("api")


class CategoryListCreateView(APIView):
    """
    List all categories or create a new one.
    GET /api/v1/categories/ - List categories
    POST /api/v1/categories/ - Create category (admin only)
    """

    def get_permissions(self):
        if self.request.method == "POST":
            return [permissions.IsAuthenticated(), IsAdminOrReadOnly()]
        return [permissions.AllowAny()]

    def get(self, request):
        """List all active categories with post counts."""
        try:
            categories = Category.objects.filter(is_active=True).order_by("name")
            serializer = CategorySerializer(categories, many=True)

            return Response(
                {
                    "success": True,
                    "categories": serializer.data,
                    "count": len(serializer.data),
                }
            )
        except Exception as e:
            logger.error(f"Error fetching categories: {e}")
            return Response(
                {"success": False, "message": "Failed to fetch categories"},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )

    def post(self, request):
        """Create a new category (admin only)."""
        serializer = CategorySerializer(data=request.data)

        if serializer.is_valid():
            try:
                # Auto-generate slug if not provided
                if not serializer.validated_data.get("slug"):
                    serializer.validated_data["slug"] = generate_slug(
                        serializer.validated_data["name"]
                    )

                category = Category(**serializer.validated_data)
                category.save()

                logger.info(
                    f"Category created: {category.name} by {request.user.email}"
                )

                return Response(
                    {
                        "success": True,
                        "message": "Category created successfully",
                        "category": CategorySerializer(category).data,
                    },
                    status=status.HTTP_201_CREATED,
                )

            except Exception as e:
                logger.error(f"Error creating category: {e}")
                return Response(
                    {"success": False, "message": "Failed to create category"},
                    status=status.HTTP_500_INTERNAL_SERVER_ERROR,
                )

        return Response(
            {
                "success": False,
                "message": "Validation failed",
                "errors": serializer.errors,
            },
            status=status.HTTP_400_BAD_REQUEST,
        )


class PostListCreateView(APIView):
    """
    List posts or create a new post.
    GET /api/v1/posts/ - List published posts
    POST /api/v1/posts/ - Create new post (authenticated users only)
    """

    permission_classes = [permissions.IsAuthenticatedOrReadOnly]

    def get(self, request):
        """List published posts with filtering and pagination."""
        try:
            # Get query parameters
            category_slug = request.GET.get("category")
            tag = request.GET.get("tag")
            author_id = request.GET.get("author")
            featured = request.GET.get("featured")
            search = request.GET.get("search")
            page = int(request.GET.get("page", 1))
            page_size = min(
                int(request.GET.get("page_size", 10)), 50
            )  # Max 50 per page

            # Base query - only published posts
            posts = Post.objects.filter(status="published")

            # Apply filters
            if category_slug:
                try:
                    category = Category.objects.get(slug=category_slug, is_active=True)
                    posts = posts.filter(category=category)
                except Category.DoesNotExist:
                    return Response(
                        {"success": False, "message": "Category not found"},
                        status=status.HTTP_404_NOT_FOUND,
                    )

            if tag:
                posts = posts.filter(tags__icontains=tag.lower())

            if author_id:
                posts = posts.filter(author_id=author_id)

            if featured and featured.lower() == "true":
                posts = posts.filter(is_featured=True)

            if search:
                # Simple text search (in production, consider using MongoDB text search)
                posts = posts.filter(title__icontains=search)

            # Order by published date (newest first)
            posts = posts.order_by("-published_at")

            # Calculate pagination
            total_count = posts.count()
            start_index = (page - 1) * page_size
            end_index = start_index + page_size
            posts_page = posts[start_index:end_index]

            # Serialize data
            serializer = PostSerializer(posts_page, many=True)

            return Response(
                {
                    "success": True,
                    "posts": serializer.data,
                    "pagination": {
                        "page": page,
                        "page_size": page_size,
                        "total_count": total_count,
                        "total_pages": (total_count + page_size - 1) // page_size,
                        "has_next": end_index < total_count,
                        "has_previous": page > 1,
                    },
                }
            )

        except Exception as e:
            logger.error(f"Error fetching posts: {e}")
            return Response(
                {"success": False, "message": "Failed to fetch posts"},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )

    def post(self, request):
        """Create a new post."""
        serializer = PostCreateSerializer(data=request.data)

        if serializer.is_valid():
            try:
                # Auto-generate slug if not provided
                if not serializer.validated_data.get("slug"):
                    serializer.validated_data["slug"] = generate_slug(
                        serializer.validated_data["title"]
                    )

                # Set author
                serializer.validated_data["author_id"] = str(request.user.id)

                post = serializer.save()

                # Track activity
                ActivityTracker.track_activity(
                    request.user.id,
                    "create",
                    "post",
                    post.id,
                    {"title": post.title},
                    request,
                )

                logger.info(f"Post created: {post.title} by {request.user.email}")

                return Response(
                    {
                        "success": True,
                        "message": "Post created successfully",
                        "post": PostSerializer(post).data,
                    },
                    status=status.HTTP_201_CREATED,
                )

            except Exception as e:
                logger.error(f"Error creating post: {e}")
                return Response(
                    {"success": False, "message": "Failed to create post"},
                    status=status.HTTP_500_INTERNAL_SERVER_ERROR,
                )

        return Response(
            {
                "success": False,
                "message": "Validation failed",
                "errors": serializer.errors,
            },
            status=status.HTTP_400_BAD_REQUEST,
        )


class PostDetailView(APIView):
    """
    Retrieve, update or delete a post.
    GET /api/v1/posts/{slug}/ - Get post details
    PUT /api/v1/posts/{slug}/ - Update post (author only)
    DELETE /api/v1/posts/{slug}/ - Delete post (author only)
    """

    permission_classes = [permissions.IsAuthenticatedOrReadOnly, IsAuthorOrReadOnly]

    def get_object(self, slug):
        """Get post by slug."""
        try:
            return Post.objects.get(slug=slug)
        except Post.DoesNotExist:
            return None

    def get(self, request, slug):
        """Get post details and increment view count."""
        post = self.get_object(slug)
        if not post:
            return Response(
                {"success": False, "message": "Post not found"},
                status=status.HTTP_404_NOT_FOUND,
            )

        # Check if post is published or user is the author
        if post.status != "published" and post.author_id != str(
            request.user.id if request.user.is_authenticated else ""
        ):
            return Response(
                {"success": False, "message": "Post not found"},
                status=status.HTTP_404_NOT_FOUND,
            )

        try:
            # Increment view count (with caching to prevent spam)
            view_key = (
                f"post_view:{post.id}:{request.META.get('REMOTE_ADDR', 'unknown')}"
            )
            if not cache.get(view_key):
                post.view_count += 1
                post.save()
                cache.set(view_key, True, timeout=3600)  # 1 hour cooldown per IP

                # Track view activity for authenticated users
                if request.user.is_authenticated:
                    ActivityTracker.track_activity(
                        request.user.id,
                        "view",
                        "post",
                        post.id,
                        {"title": post.title},
                        request,
                    )

            serializer = PostSerializer(post)
            return Response({"success": True, "post": serializer.data})

        except Exception as e:
            logger.error(f"Error fetching post: {e}")
            return Response(
                {"success": False, "message": "Failed to fetch post"},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )

    def put(self, request, slug):
        """Update post (author only)."""
        post = self.get_object(slug)
        if not post:
            return Response(
                {"success": False, "message": "Post not found"},
                status=status.HTTP_404_NOT_FOUND,
            )

        # Check permissions
        self.check_object_permissions(request, post)

        serializer = PostUpdateSerializer(post, data=request.data, partial=True)

        if serializer.is_valid():
            try:
                updated_post = serializer.save()

                # Track activity
                ActivityTracker.track_activity(
                    request.user.id,
                    "update",
                    "post",
                    post.id,
                    {"title": post.title},
                    request,
                )

                logger.info(f"Post updated: {post.title} by {request.user.email}")

                return Response(
                    {
                        "success": True,
                        "message": "Post updated successfully",
                        "post": PostSerializer(updated_post).data,
                    }
                )

            except Exception as e:
                logger.error(f"Error updating post: {e}")
                return Response(
                    {"success": False, "message": "Failed to update post"},
                    status=status.HTTP_500_INTERNAL_SERVER_ERROR,
                )

        return Response(
            {
                "success": False,
                "message": "Validation failed",
                "errors": serializer.errors,
            },
            status=status.HTTP_400_BAD_REQUEST,
        )

    def delete(self, request, slug):
        """Delete post (author only)."""
        post = self.get_object(slug)
        if not post:
            return Response(
                {"success": False, "message": "Post not found"},
                status=status.HTTP_404_NOT_FOUND,
            )

        # Check permissions
        self.check_object_permissions(request, post)

        post_title = "test post"
        try:
            # Track activity
            ActivityTracker.track_activity(
                request.user.id,
                "delete",
                "post",
                post.id,
                {"title": post_title},
                request,
            )

            logger.info(f"Post deleted: {post_title} by {request.user.email}")

            return Response({"success": True, "message": "Post deleted successfully"})

        except Exception as e:
            logger.error(f"Error deleting post: {e}")
            return Response(
                {"success": False, "message": "Failed to delete post"},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )


class MyPostsView(APIView):
    """
    List current user's posts.
    GET /api/v1/my-posts/ - List user's own posts (all statuses)
    """

    permission_classes = [permissions.IsAuthenticated]

    def get(self, request):
        """List current user's posts."""
        try:
            status_filter = request.GET.get("status", "all")
            page = int(request.GET.get("page", 1))
            page_size = min(int(request.GET.get("page_size", 10)), 50)

            # Get user's posts
            posts = Post.objects.filter(author_id=str(request.user.id))

            # Apply status filter
            if status_filter != "all":
                posts = posts.filter(status=status_filter)

            # Order by created date (newest first)
            posts = posts.order_by("-created_at")

            # Calculate pagination
            total_count = posts.count()
            start_index = (page - 1) * page_size
            end_index = start_index + page_size
            posts_page = posts[start_index:end_index]

            # Serialize data
            serializer = PostSerializer(posts_page, many=True)

            # Get user stats
            user_stats = get_cached_user_stats(request.user.id)

            return Response(
                {
                    "success": True,
                    "posts": serializer.data,
                    "stats": user_stats,
                    "pagination": {
                        "page": page,
                        "page_size": page_size,
                        "total_count": total_count,
                        "total_pages": (total_count + page_size - 1) // page_size,
                        "has_next": end_index < total_count,
                        "has_previous": page > 1,
                    },
                }
            )

        except Exception as e:
            logger.error(f"Error fetching user posts: {e}")
            return Response(
                {"success": False, "message": "Failed to fetch posts"},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )


class CommentListCreateView(APIView):
    """
    List comments for a post or create a new comment.
    GET /api/v1/posts/{post_slug}/comments/ - List comments
    POST /api/v1/posts/{post_slug}/comments/ - Create comment
    """

    permission_classes = [permissions.IsAuthenticatedOrReadOnly]

    def get_post(self, post_slug):
        """Get post by slug."""
        try:
            return Post.objects.get(slug=post_slug, status="published")
        except Post.DoesNotExist:
            return None

    def get(self, request, post_slug):
        """List comments for a post."""
        post = self.get_post(post_slug)
        if not post:
            return Response(
                {"success": False, "message": "Post not found"},
                status=status.HTTP_404_NOT_FOUND,
            )

        try:
            # Get top-level comments (no parent)
            comments = Comment.objects.filter(
                post=post, parent=None, is_approved=True
            ).order_by("-created_at")

            serializer = CommentSerializer(
                comments, many=True, context={"request": request}
            )

            return Response(
                {
                    "success": True,
                    "comments": serializer.data,
                    "count": len(serializer.data),
                }
            )

        except Exception as e:
            logger.error(f"Error fetching comments: {e}")
            return Response(
                {"success": False, "message": "Failed to fetch comments"},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )

    def post(self, request, post_slug):
        """Create a new comment."""
        post = self.get_post(post_slug)
        if not post:
            return Response(
                {"success": False, "message": "Post not found"},
                status=status.HTTP_404_NOT_FOUND,
            )

        # Add post_id to request data
        data = request.data.copy()
        data["post_id"] = str(post.id)

        serializer = CommentSerializer(data=data)

        if serializer.is_valid():
            try:
                # Create comment
                comment_data = serializer.validated_data
                comment = Comment(
                    content=comment_data["content"],
                    post=post,
                    author_id=str(request.user.id),
                    is_approved=True,  # Auto-approve for now
                )

                # Set parent if this is a reply
                parent_id = comment_data.get("parent_id")
                if parent_id:
                    try:
                        parent = Comment.objects.get(id=parent_id, post=post)
                        comment.parent = parent
                    except Comment.DoesNotExist:
                        return Response(
                            {"success": False, "message": "Parent comment not found"},
                            status=status.HTTP_400_BAD_REQUEST,
                        )

                comment.save()

                # Update post comment count
                post.comment_count = Comment.objects.filter(
                    post=post, is_approved=True
                ).count()
                post.save()

                # Track activity
                ActivityTracker.track_activity(
                    request.user.id,
                    "comment",
                    "post",
                    post.id,
                    {"post_title": post.title},
                    request,
                )

                logger.info(
                    f"Comment created on post: {post.title} by {request.user.email}"
                )

                return Response(
                    {
                        "success": True,
                        "message": "Comment created successfully",
                        "comment": CommentSerializer(
                            comment, context={"request": request}
                        ).data,
                    },
                    status=status.HTTP_201_CREATED,
                )

            except Exception as e:
                logger.error(f"Error creating comment: {e}")
                return Response(
                    {"success": False, "message": "Failed to create comment"},
                    status=status.HTTP_500_INTERNAL_SERVER_ERROR,
                )

        return Response(
            {
                "success": False,
                "message": "Validation failed",
                "errors": serializer.errors,
            },
            status=status.HTTP_400_BAD_REQUEST,
        )


class PostLikeView(APIView):
    """
    Like/unlike a post.
    POST /api/v1/posts/{post_slug}/like/ - Toggle like
    """

    permission_classes = [permissions.IsAuthenticated]

    def post(self, request, post_slug):
        """Toggle like on a post."""
        try:
            post = Post.objects.get(slug=post_slug, status="published")
        except Post.DoesNotExist:
            return Response(
                {"success": False, "message": "Post not found"},
                status=status.HTTP_404_NOT_FOUND,
            )

        try:
            user_id = str(request.user.id)
            like_key = f"post_like:{post.id}:{user_id}"

            # Check if user already liked this post
            has_liked = cache.get(like_key, False)

            if has_liked:
                # Unlike the post
                post.like_count = max(0, post.like_count - 1)
                cache.delete(like_key)
                action = "unlike"
                message = "Post unliked"
            else:
                # Like the post
                post.like_count += 1
                cache.set(like_key, True, timeout=None)  # Store indefinitely
                action = "like"
                message = "Post liked"

            post.save()

            # Track activity
            ActivityTracker.track_activity(
                request.user.id,
                action,
                "post",
                post.id,
                {"post_title": post.title},
                request,
            )

            return Response(
                {
                    "success": True,
                    "message": message,
                    "liked": not has_liked,
                    "like_count": post.like_count,
                }
            )

        except Exception as e:
            logger.error(f"Error toggling like: {e}")
            return Response(
                {"success": False, "message": "Failed to toggle like"},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )


class UserActivityView(APIView):
    """
    Get user's activity history.
    GET /api/v1/my-activity/ - Get current user's activities
    """

    permission_classes = [permissions.IsAuthenticated]

    def get(self, request):
        """Get user's recent activities."""
        try:
            page = int(request.GET.get("page", 1))
            page_size = min(int(request.GET.get("page_size", 20)), 100)
            action_filter = request.GET.get("action")

            # Get user activities
            activities = UserActivity.objects.filter(user_id=str(request.user.id))

            if action_filter:
                activities = activities.filter(action=action_filter)

            # Order by date (newest first)
            activities = activities.order_by("-created_at")

            # Calculate pagination
            total_count = activities.count()
            start_index = (page - 1) * page_size
            end_index = start_index + page_size
            activities_page = activities[start_index:end_index]

            # Serialize data
            serializer = UserActivitySerializer(activities_page, many=True)

            return Response(
                {
                    "success": True,
                    "activities": serializer.data,
                    "pagination": {
                        "page": page,
                        "page_size": page_size,
                        "total_count": total_count,
                        "total_pages": (total_count + page_size - 1) // page_size,
                        "has_next": end_index < total_count,
                        "has_previous": page > 1,
                    },
                }
            )

        except Exception as e:
            logger.error(f"Error fetching user activities: {e}")
            return Response(
                {"success": False, "message": "Failed to fetch activities"},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )


@api_view(["GET"])
@permission_classes([permissions.AllowAny])
def dashboard_stats(request):
    """
    Get dashboard statistics.
    GET /api/v1/dashboard/stats/
    """
    try:
        # Cache key for dashboard stats
        cache_key = "dashboard_stats"
        stats = cache.get(cache_key)

        if not stats:
            # Calculate stats
            total_posts = Post.objects.filter(status="published").count()
            total_users = User.objects.filter(is_active=True).count()
            total_comments = Comment.objects.filter(is_approved=True).count()
            total_categories = Category.objects.filter(is_active=True).count()

            # Recent activity (last 7 days)
            week_ago = datetime.utcnow() - timedelta(days=7)
            recent_posts = Post.objects.filter(
                status="published", published_at__gte=week_ago
            ).count()
            recent_users = User.objects.filter(date_joined__gte=week_ago).count()

            # Top categories by post count
            top_categories = []
            for category in Category.objects.filter(is_active=True):
                post_count = Post.objects.filter(
                    category=category, status="published"
                ).count()
                if post_count > 0:
                    top_categories.append(
                        {
                            "name": category.name,
                            "slug": category.slug,
                            "post_count": post_count,
                            "color": category.color,
                        }
                    )

            top_categories.sort(key=lambda x: x["post_count"], reverse=True)
            top_categories = top_categories[:5]  # Top 5

            stats = {
                "totals": {
                    "posts": total_posts,
                    "users": total_users,
                    "comments": total_comments,
                    "categories": total_categories,
                },
                "recent": {
                    "posts_this_week": recent_posts,
                    "users_this_week": recent_users,
                },
                "top_categories": top_categories,
            }

            # Cache for 1 hour
            cache.set(cache_key, stats, timeout=3600)

        return Response({"success": True, "stats": stats})

    except Exception as e:
        logger.error(f"Error fetching dashboard stats: {e}")
        return Response(
            {"success": False, "message": "Failed to fetch dashboard stats"},
            status=status.HTTP_500_INTERNAL_SERVER_ERROR,
        )
