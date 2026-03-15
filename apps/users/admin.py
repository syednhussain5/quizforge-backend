from django.contrib import admin
from django.contrib.auth.admin import UserAdmin
from .models import User, Badge, UserBadge, Notification


@admin.register(User)
class CustomUserAdmin(UserAdmin):
    list_display = ('username', 'email', 'role', 'xp', 'level', 'current_streak', 'total_quizzes_taken')
    list_filter = ('role', 'level')
    search_fields = ('username', 'email')
    ordering = ('-xp',)
    fieldsets = UserAdmin.fieldsets + (
        ('Gamification', {'fields': ('xp', 'level', 'current_streak', 'longest_streak')}),
        ('Stats', {'fields': ('total_quizzes_taken', 'total_correct_answers', 'total_questions_answered')}),
        ('Settings', {'fields': ('role', 'bio', 'avatar', 'preferred_difficulty')}),
    )


@admin.register(Badge)
class BadgeAdmin(admin.ModelAdmin):
    list_display = ('name', 'badge_type', 'threshold', 'xp_reward', 'icon')


@admin.register(UserBadge)
class UserBadgeAdmin(admin.ModelAdmin):
    list_display = ('user', 'badge', 'earned_at')


@admin.register(Notification)
class NotificationAdmin(admin.ModelAdmin):
    list_display = ('user', 'notif_type', 'title', 'is_read', 'created_at')
