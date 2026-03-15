from django.db import models
from django.conf import settings


class TopicPerformance(models.Model):
    """Aggregated per-user performance per topic tag."""
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='topic_performances')
    topic = models.CharField(max_length=200)
    total_questions = models.IntegerField(default=0)
    correct_answers = models.IntegerField(default=0)
    avg_time_seconds = models.FloatField(default=0.0)
    last_attempted = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = 'topic_performances'
        unique_together = ('user', 'topic')
        ordering = ['-total_questions']

    @property
    def accuracy(self):
        if self.total_questions == 0:
            return 0
        return round((self.correct_answers / self.total_questions) * 100, 1)

    def __str__(self):
        return f"{self.user.username} - {self.topic} ({self.accuracy}%)"


class DailyStats(models.Model):
    """Daily snapshot of a user's quiz activity."""
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='daily_stats')
    date = models.DateField()
    quizzes_taken = models.IntegerField(default=0)
    questions_answered = models.IntegerField(default=0)
    correct_answers = models.IntegerField(default=0)
    xp_earned = models.IntegerField(default=0)
    time_spent_seconds = models.IntegerField(default=0)

    class Meta:
        db_table = 'daily_stats'
        unique_together = ('user', 'date')
        ordering = ['-date']
