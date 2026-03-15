from django.contrib import admin
from .models import TopicPerformance, DailyStats


@admin.register(TopicPerformance)
class TopicPerformanceAdmin(admin.ModelAdmin):
    list_display = ('user', 'topic', 'total_questions', 'correct_answers', 'accuracy')

    def accuracy(self, obj):
        return f"{obj.accuracy}%"


@admin.register(DailyStats)
class DailyStatsAdmin(admin.ModelAdmin):
    list_display = ('user', 'date', 'quizzes_taken', 'xp_earned')
