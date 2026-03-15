import uuid
from django.db import models
from django.conf import settings


class Quiz(models.Model):
    """A quiz with metadata. Can be AI-generated or user-created."""

    DIFFICULTY_CHOICES = [
        ('easy', 'Easy'),
        ('medium', 'Medium'),
        ('hard', 'Hard'),
        ('adaptive', 'Adaptive'),
    ]

    STATUS_CHOICES = [
        ('generating', 'Generating'),
        ('ready', 'Ready'),
        ('failed', 'Failed'),
    ]

    QUESTION_TYPE_CHOICES = [
        ('mcq', 'Multiple Choice'),
        ('true_false', 'True/False'),
        ('multi_select', 'Multi Select'),
    ]

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    creator = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='created_quizzes'
    )
    title = models.CharField(max_length=300)
    topic = models.CharField(max_length=200)
    description = models.TextField(blank=True)
    difficulty = models.CharField(max_length=20, choices=DIFFICULTY_CHOICES, default='medium')
    question_count = models.IntegerField(default=10)
    time_limit_minutes = models.IntegerField(null=True, blank=True)  # None = untimed
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='generating')
    is_public = models.BooleanField(default=True)
    is_ai_generated = models.BooleanField(default=True)
    allow_review = models.BooleanField(default=True)  # Show answers after quiz
    randomize_questions = models.BooleanField(default=True)
    randomize_options = models.BooleanField(default=True)
    source_material = models.TextField(blank=True)  # For PDF/notes-based generation
    tags = models.JSONField(default=list)
    play_count = models.IntegerField(default=0)
    average_score = models.FloatField(default=0.0)

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = 'quizzes'
        ordering = ['-created_at']

    def __str__(self):
        return f"{self.title} ({self.topic})"

    def update_stats(self, new_score):
        """Recalculate average score after a new attempt."""
        total = self.average_score * self.play_count
        self.play_count += 1
        self.average_score = (total + new_score) / self.play_count
        self.save(update_fields=['play_count', 'average_score'])


class Question(models.Model):
    """A single question belonging to a quiz."""

    DIFFICULTY_CHOICES = [
        ('easy', 'Easy'),
        ('medium', 'Medium'),
        ('hard', 'Hard'),
    ]

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    quiz = models.ForeignKey(Quiz, on_delete=models.CASCADE, related_name='questions')
    text = models.TextField()
    question_type = models.CharField(
        max_length=20,
        choices=[('mcq', 'MCQ'), ('true_false', 'True/False'), ('multi_select', 'Multi Select')],
        default='mcq'
    )
    difficulty = models.CharField(max_length=10, choices=DIFFICULTY_CHOICES, default='medium')
    explanation = models.TextField(blank=True)  # Shown in learning mode
    image_url = models.URLField(blank=True)  # For image-based questions
    order = models.IntegerField(default=0)
    topic_tag = models.CharField(max_length=100, blank=True)  # Sub-topic for analytics

    class Meta:
        db_table = 'questions'
        ordering = ['order']

    def __str__(self):
        return self.text[:80]


class Option(models.Model):
    """A multiple choice option for a question."""

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    question = models.ForeignKey(Question, on_delete=models.CASCADE, related_name='options')
    text = models.TextField()
    is_correct = models.BooleanField(default=False)
    order = models.IntegerField(default=0)

    class Meta:
        db_table = 'options'
        ordering = ['order']

    def __str__(self):
        return f"{'✓' if self.is_correct else '✗'} {self.text[:50]}"


class QuizAttempt(models.Model):
    """A user's attempt at a quiz — tracks the full session."""

    STATUS_CHOICES = [
        ('in_progress', 'In Progress'),
        ('completed', 'Completed'),
        ('abandoned', 'Abandoned'),
        ('timed_out', 'Timed Out'),
    ]

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='quiz_attempts'
    )
    quiz = models.ForeignKey(Quiz, on_delete=models.CASCADE, related_name='attempts')
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='in_progress')
    score = models.FloatField(default=0.0)  # Percentage 0-100
    correct_count = models.IntegerField(default=0)
    total_questions = models.IntegerField(default=0)
    xp_earned = models.IntegerField(default=0)
    time_taken_seconds = models.IntegerField(null=True, blank=True)
    question_order = models.JSONField(default=list)  # Stores shuffled order of question UUIDs
    # Anti-cheat: track tab switches
    tab_switches = models.IntegerField(default=0)
    is_adaptive = models.BooleanField(default=False)

    started_at = models.DateTimeField(auto_now_add=True)
    completed_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        db_table = 'quiz_attempts'
        ordering = ['-started_at']

    def __str__(self):
        return f"{self.user.username} - {self.quiz.title} ({self.score}%)"


class Answer(models.Model):
    """A user's answer to a single question within an attempt."""

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    attempt = models.ForeignKey(QuizAttempt, on_delete=models.CASCADE, related_name='answers')
    question = models.ForeignKey(Question, on_delete=models.CASCADE)
    selected_options = models.ManyToManyField(Option, blank=True)
    is_correct = models.BooleanField(default=False)
    time_taken_seconds = models.IntegerField(default=0)
    # For adaptive: what difficulty was shown
    shown_difficulty = models.CharField(max_length=10, default='medium')

    answered_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = 'answers'

    def __str__(self):
        return f"{'✓' if self.is_correct else '✗'} {self.question.text[:50]}"


class QuizRoom(models.Model):
    """Multiplayer quiz room for live 1v1 or group battles."""

    STATUS_CHOICES = [
        ('waiting', 'Waiting'),
        ('in_progress', 'In Progress'),
        ('finished', 'Finished'),
    ]

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    code = models.CharField(max_length=8, unique=True)  # Join code like "QUIZ1234"
    quiz = models.ForeignKey(Quiz, on_delete=models.CASCADE, related_name='rooms')
    host = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='hosted_rooms'
    )
    participants = models.ManyToManyField(
        settings.AUTH_USER_MODEL,
        through='RoomParticipant',
        related_name='joined_rooms'
    )
    max_participants = models.IntegerField(default=10)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='waiting')
    current_question_index = models.IntegerField(default=0)

    created_at = models.DateTimeField(auto_now_add=True)
    started_at = models.DateTimeField(null=True, blank=True)
    finished_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        db_table = 'quiz_rooms'

    def __str__(self):
        return f"Room {self.code} - {self.quiz.title}"


class RoomParticipant(models.Model):
    """Tracks scores in a multiplayer room."""
    room = models.ForeignKey(QuizRoom, on_delete=models.CASCADE)
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE)
    score = models.IntegerField(default=0)
    answers_given = models.IntegerField(default=0)
    joined_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = 'room_participants'
        unique_together = ('room', 'user')
