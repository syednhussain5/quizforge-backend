from rest_framework import generics, permissions, status
from rest_framework.response import Response
from rest_framework.views import APIView
from rest_framework_simplejwt.views import TokenObtainPairView
from django.db.models import Q
from .models import User, Badge, UserBadge, Notification
from .serializers import (
    RegisterSerializer, CustomTokenObtainPairSerializer,
    UserProfileSerializer, UserUpdateSerializer,
    LeaderboardSerializer, NotificationSerializer, BadgeSerializer, UserBadgeSerializer
)


class RegisterView(generics.CreateAPIView):
    queryset = User.objects.all()
    serializer_class = RegisterSerializer
    permission_classes = [permissions.AllowAny]


class CustomTokenObtainPairView(TokenObtainPairView):
    serializer_class = CustomTokenObtainPairSerializer


class UserProfileView(generics.RetrieveUpdateAPIView):
    serializer_class = UserProfileSerializer

    def get_object(self):
        return self.request.user

    def get_serializer_class(self):
        if self.request.method in ('PUT', 'PATCH'):
            return UserUpdateSerializer
        return UserProfileSerializer


class PublicProfileView(generics.RetrieveAPIView):
    serializer_class = UserProfileSerializer
    queryset = User.objects.all()
    permission_classes = [permissions.IsAuthenticatedOrReadOnly]
    lookup_field = 'username'


class LeaderboardView(generics.ListAPIView):
    serializer_class = LeaderboardSerializer
    permission_classes = [permissions.IsAuthenticatedOrReadOnly]

    def get_queryset(self):
        period = self.request.query_params.get('period', 'all')
        queryset = User.objects.all()

        # Sort options
        sort_by = self.request.query_params.get('sort', 'xp')
        if sort_by == 'accuracy':
            # We can't sort by property directly, so sort by ratio
            queryset = queryset.filter(total_questions_answered__gt=0)
            # Python sort after queryset
        elif sort_by == 'streak':
            queryset = queryset.order_by('-current_streak')
        elif sort_by == 'quizzes':
            queryset = queryset.order_by('-total_quizzes_taken')
        else:
            queryset = queryset.order_by('-xp')

        return queryset[:100]


class UserBadgesView(generics.ListAPIView):
    serializer_class = BadgeSerializer

    def get_queryset(self):
        return Badge.objects.all()

    def list(self, request, *args, **kwargs):
        all_badges = Badge.objects.all()
        earned_ids = UserBadge.objects.filter(
            user=request.user
        ).values_list('badge_id', flat=True)

        data = []
        for badge in all_badges:
            badge_data = BadgeSerializer(badge).data
            badge_data['earned'] = badge.id in earned_ids
            data.append(badge_data)
        return Response(data)


class NotificationsView(generics.ListAPIView):
    serializer_class = NotificationSerializer

    def get_queryset(self):
        return Notification.objects.filter(user=self.request.user)


class MarkNotificationReadView(APIView):
    def post(self, request):
        Notification.objects.filter(user=request.user).update(is_read=True)
        return Response({'status': 'ok'})


class UserSearchView(generics.ListAPIView):
    serializer_class = LeaderboardSerializer

    def get_queryset(self):
        query = self.request.query_params.get('q', '')
        if not query:
            return User.objects.none()
        return User.objects.filter(
            Q(username__icontains=query) | Q(email__icontains=query)
        )[:10]
