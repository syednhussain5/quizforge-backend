from django.urls import path
from rest_framework_simplejwt.views import TokenRefreshView, TokenBlacklistView
from . import views

urlpatterns = [
    path('register/', views.RegisterView.as_view(), name='register'),
    path('login/', views.CustomTokenObtainPairView.as_view(), name='login'),
    path('token/refresh/', TokenRefreshView.as_view(), name='token_refresh'),
    path('logout/', TokenBlacklistView.as_view(), name='logout'),
    path('me/', views.UserProfileView.as_view(), name='profile'),
    path('users/<str:username>/', views.PublicProfileView.as_view(), name='public-profile'),
    path('leaderboard/', views.LeaderboardView.as_view(), name='leaderboard'),
    path('badges/', views.UserBadgesView.as_view(), name='badges'),
    path('notifications/', views.NotificationsView.as_view(), name='notifications'),
    path('notifications/read/', views.MarkNotificationReadView.as_view(), name='notifications-read'),
    path('search/', views.UserSearchView.as_view(), name='user-search'),
]
