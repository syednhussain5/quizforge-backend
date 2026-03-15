from django.contrib import admin
from .models import Quiz, Question, Option, QuizAttempt, Answer, QuizRoom


class OptionInline(admin.TabularInline):
    model = Option
    extra = 4


class QuestionInline(admin.TabularInline):
    model = Question
    extra = 0
    show_change_link = True


@admin.register(Quiz)
class QuizAdmin(admin.ModelAdmin):
    list_display = ('title', 'topic', 'difficulty', 'status', 'play_count', 'average_score', 'creator', 'created_at')
    list_filter = ('status', 'difficulty', 'is_public', 'is_ai_generated')
    search_fields = ('title', 'topic')
    inlines = [QuestionInline]


@admin.register(Question)
class QuestionAdmin(admin.ModelAdmin):
    list_display = ('text', 'quiz', 'question_type', 'difficulty')
    list_filter = ('question_type', 'difficulty')
    inlines = [OptionInline]


@admin.register(QuizAttempt)
class QuizAttemptAdmin(admin.ModelAdmin):
    list_display = ('user', 'quiz', 'status', 'score', 'correct_count', 'total_questions', 'started_at')
    list_filter = ('status',)


@admin.register(QuizRoom)
class QuizRoomAdmin(admin.ModelAdmin):
    list_display = ('code', 'quiz', 'host', 'status', 'created_at')
