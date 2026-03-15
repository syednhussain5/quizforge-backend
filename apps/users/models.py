from django.contrib.auth.models import AbstractUser
from django.db import models
from django.utils import timezone


class User(AbstractUser):
    """Extended user model with gamification and profile features."""

    ROLE_CHOICES = [
        ('student', 'Student'),
        ('teacher', 'Teacher'),
        ('admin', 'Admin'),
    ]

    email = models.EmailField(unique=True)
    role = models.CharField(max_length=20, choices=ROLE_CHOICES, default='student')
    avatar = models.ImageField(upload_to='avatars/', null=True, blank=True)
    bio = models.TextField(blank=True)

    # Gamification
    xp = models.IntegerField(default=0)
    level = models.IntegerField(default=1)
    total_quizzes_taken = models.IntegerField(default=0)
    total_correct_answers = models.IntegerField(default=0)
    total_questions_answered = models.IntegerField(default=0)

    # Streaks
    current_streak = models.IntegerField(default=0)
    longest_streak = models.IntegerField(default=0)
    last_active_date = models.DateField(null=True, blank=True)

    # Settings
    receive_notifications = models.BooleanField(default=True)
    preferred_difficulty = models.CharField(
        max_length=20,
        choices=[('easy', 'Easy'), ('medium', 'Medium'), ('hard', 'Hard')],
        default='medium'
    )

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    USERNAME_FIELD = 'email'
    REQUIRED_FIELDS = ['username']

    class Meta:
        db_table = 'users'
        ordering = ['-xp']

    def __str__(self):
        return f"{self.username} ({self.email})"

    @property
    def accuracy(self):
        if self.total_questions_answered == 0:
            return 0
        return round((self.total_correct_answers / self.total_questions_answered) * 100, 1)

    def add_xp(self, amount):
        """Add XP and level up if threshold reached."""
        self.xp += amount
        # Level up every 500 XP
        new_level = (self.xp // 500) + 1
        if new_level > self.level:
            self.level = new_level
        self.save(update_fields=['xp', 'level'])

    def update_streak(self):
        """Update daily streak."""
        today = timezone.now().date()
        if self.last_active_date is None:
            self.current_streak = 1
        elif self.last_active_date == today:
            return  # Already active today
        elif (today - self.last_active_date).days == 1:
            self.current_streak += 1
        else:
            self.current_streak = 1

        self.last_active_date = today
        if self.current_streak > self.longest_streak:
            self.longest_streak = self.current_streak
        self.save(update_fields=['current_streak', 'longest_streak', 'last_active_date'])


class Badge(models.Model):
    """Achievement badges that users can earn."""

    BADGE_TYPES = [
        ('quiz_count', 'Quiz Count'),
        ('xp', 'XP Milestone'),
        ('streak', 'Streak'),
        ('accuracy', 'Accuracy'),
        ('speed', 'Speed'),
        ('special', 'Special'),
    ]

    name = models.CharField(max_length=100)
    description = models.TextField()
    badge_type = models.CharField(max_length=20, choices=BADGE_TYPES)
    threshold = models.IntegerField()
    icon = models.CharField(max_length=50, default='🏆')  # Emoji or icon name
    xp_reward = models.IntegerField(default=50)

    class Meta:
        db_table = 'badges'

    def __str__(self):
        return self.name


class UserBadge(models.Model):
    """Junction table for user-earned badges."""
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='user_badges')
    badge = models.ForeignKey(Badge, on_delete=models.CASCADE)
    earned_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = 'user_badges'
        unique_together = ('user', 'badge')


class Notification(models.Model):
    """User notifications."""

    NOTIF_TYPES = [
        ('badge_earned', 'Badge Earned'),
        ('level_up', 'Level Up'),
        ('streak', 'Streak'),
        ('challenge', 'Challenge'),
        ('quiz_result', 'Quiz Result'),
    ]

    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='notifications')
    notif_type = models.CharField(max_length=30, choices=NOTIF_TYPES)
    title = models.CharField(max_length=200)
    message = models.TextField()
    is_read = models.BooleanField(default=False)
    data = models.JSONField(default=dict)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = 'notifications'
        ordering = ['-created_at']
