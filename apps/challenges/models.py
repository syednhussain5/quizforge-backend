from django.db import models
from django.conf import settings


class DailyChallenge(models.Model):
    """One daily challenge quiz per day."""
    quiz = models.ForeignKey('quizzes.Quiz', on_delete=models.CASCADE)
    date = models.DateField(unique=True)
    participants = models.ManyToManyField(
        settings.AUTH_USER_MODEL,
        through='DailyChallengeAttempt',
        related_name='daily_challenges'
    )

    class Meta:
        db_table = 'daily_challenges'
        ordering = ['-date']

    def __str__(self):
        return f"Daily Challenge {self.date}"


class DailyChallengeAttempt(models.Model):
    challenge = models.ForeignKey(DailyChallenge, on_delete=models.CASCADE)
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE)
    score = models.FloatField(default=0)
    xp_earned = models.IntegerField(default=0)
    completed_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = 'daily_challenge_attempts'
        unique_together = ('challenge', 'user')
