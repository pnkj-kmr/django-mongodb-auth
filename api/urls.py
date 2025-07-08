from django.urls import path
from .views import (
    CategoryListCreateView,
    PostListCreateView,
    PostDetailView,
    MyPostsView,
    CommentListCreateView,
    PostLikeView,
    UserActivityView,
    dashboard_stats,
)

urlpatterns = [
    # Categories
    path("categories/", CategoryListCreateView.as_view(), name="category-list-create"),
    # Posts
    path("posts/", PostListCreateView.as_view(), name="post-list-create"),
    path("posts/<str:slug>/", PostDetailView.as_view(), name="post-detail"),
    path("my-posts/", MyPostsView.as_view(), name="my-posts"),
    # Comments
    path(
        "posts/<str:post_slug>/comments/",
        CommentListCreateView.as_view(),
        name="comment-list-create",
    ),
    # Interactions
    path("posts/<str:post_slug>/like/", PostLikeView.as_view(), name="post-like"),
    # User data
    path("my-activity/", UserActivityView.as_view(), name="user-activity"),
    # Dashboard
    path("dashboard/stats/", dashboard_stats, name="dashboard-stats"),
]
