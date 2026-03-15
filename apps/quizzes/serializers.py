import random
from rest_framework import serializers
from .models import Quiz, Question, Option, QuizAttempt, Answer, QuizRoom, RoomParticipant


class OptionSerializer(serializers.ModelSerializer):
    class Meta:
        model = Option
        fields = ('id', 'text', 'order')  # Never expose is_correct during a quiz


class OptionWithAnswerSerializer(serializers.ModelSerializer):
    """Used when reviewing completed quiz - exposes correct answer."""
    class Meta:
        model = Option
        fields = ('id', 'text', 'is_correct', 'order')


class QuestionSerializer(serializers.ModelSerializer):
    options = serializers.SerializerMethodField()

    class Meta:
        model = Question
        fields = ('id', 'text', 'question_type', 'difficulty', 'image_url', 'options', 'order')

    def get_options(self, obj):
        options = list(obj.options.all())
        if self.context.get('randomize_options', True):
            random.shuffle(options)
        return OptionSerializer(options, many=True).data


class QuestionWithAnswerSerializer(serializers.ModelSerializer):
    """Used in review/learning mode - includes correct answers and explanation."""
    options = OptionWithAnswerSerializer(many=True, read_only=True)

    class Meta:
        model = Question
        fields = ('id', 'text', 'question_type', 'difficulty', 'image_url', 'options', 'explanation', 'topic_tag', 'order')


class QuizListSerializer(serializers.ModelSerializer):
    creator_username = serializers.CharField(source='creator.username', read_only=True)
    question_count = serializers.SerializerMethodField()

    class Meta:
        model = Quiz
        fields = (
            'id', 'title', 'topic', 'difficulty', 'question_count',
            'time_limit_minutes', 'status', 'is_public', 'is_ai_generated',
            'play_count', 'average_score', 'tags', 'creator_username',
            'created_at'
        )

    def get_question_count(self, obj):
        return obj.questions.count()


class QuizDetailSerializer(serializers.ModelSerializer):
    questions = serializers.SerializerMethodField()
    creator_username = serializers.CharField(source='creator.username', read_only=True)

    class Meta:
        model = Quiz
        fields = (
            'id', 'title', 'topic', 'description', 'difficulty', 'time_limit_minutes',
            'status', 'is_public', 'allow_review', 'randomize_questions',
            'randomize_options', 'play_count', 'average_score', 'tags',
            'creator_username', 'questions', 'created_at'
        )

    def get_questions(self, obj):
        questions = list(obj.questions.all())
        if obj.randomize_questions:
            random.shuffle(questions)
        return QuestionSerializer(
            questions,
            many=True,
            context={'randomize_options': obj.randomize_options}
        ).data


class QuizCreateSerializer(serializers.ModelSerializer):
    class Meta:
        model = Quiz
        fields = (
            'title', 'topic', 'description', 'difficulty', 'question_count',
            'time_limit_minutes', 'is_public', 'allow_review',
            'randomize_questions', 'randomize_options', 'tags', 'source_material'
        )

    def validate_question_count(self, value):
        if not (5 <= value <= 20):
            raise serializers.ValidationError("Question count must be between 5 and 20.")
        return value


class AnswerSerializer(serializers.ModelSerializer):
    question_text = serializers.CharField(source='question.text', read_only=True)
    question_explanation = serializers.CharField(source='question.explanation', read_only=True)
    correct_options = OptionWithAnswerSerializer(
        source='question.options',
        many=True,
        read_only=True
    )
    selected_option_ids = serializers.SerializerMethodField()

    class Meta:
        model = Answer
        fields = (
            'id', 'question', 'question_text', 'question_explanation',
            'selected_option_ids', 'correct_options', 'is_correct',
            'time_taken_seconds', 'shown_difficulty'
        )

    def get_selected_option_ids(self, obj):
        return list(obj.selected_options.values_list('id', flat=True))


class QuizAttemptListSerializer(serializers.ModelSerializer):
    quiz_title = serializers.CharField(source='quiz.title', read_only=True)
    quiz_topic = serializers.CharField(source='quiz.topic', read_only=True)

    class Meta:
        model = QuizAttempt
        fields = (
            'id', 'quiz', 'quiz_title', 'quiz_topic', 'status', 'score',
            'correct_count', 'total_questions', 'xp_earned',
            'time_taken_seconds', 'started_at', 'completed_at'
        )


class QuizAttemptDetailSerializer(serializers.ModelSerializer):
    answers = AnswerSerializer(many=True, read_only=True)
    quiz_title = serializers.CharField(source='quiz.title', read_only=True)

    class Meta:
        model = QuizAttempt
        fields = (
            'id', 'quiz', 'quiz_title', 'status', 'score', 'correct_count',
            'total_questions', 'xp_earned', 'time_taken_seconds',
            'tab_switches', 'answers', 'started_at', 'completed_at'
        )


class SubmitAnswerSerializer(serializers.Serializer):
    question_id = serializers.UUIDField()
    selected_option_ids = serializers.ListField(child=serializers.UUIDField())
    time_taken_seconds = serializers.IntegerField(min_value=0, default=0)


class CompleteAttemptSerializer(serializers.Serializer):
    time_taken_seconds = serializers.IntegerField(min_value=0)
    tab_switches = serializers.IntegerField(min_value=0, default=0)


class RoomParticipantSerializer(serializers.ModelSerializer):
    username = serializers.CharField(source='user.username', read_only=True)
    avatar = serializers.ImageField(source='user.avatar', read_only=True)
    xp = serializers.IntegerField(source='user.xp', read_only=True)

    class Meta:
        model = RoomParticipant
        fields = ('user', 'username', 'avatar', 'xp', 'score', 'answers_given', 'joined_at')


class QuizRoomSerializer(serializers.ModelSerializer):
    participants = RoomParticipantSerializer(
        source='roomparticipant_set',
        many=True,
        read_only=True
    )
    quiz_title = serializers.CharField(source='quiz.title', read_only=True)
    host_username = serializers.CharField(source='host.username', read_only=True)
    participant_count = serializers.SerializerMethodField()

    class Meta:
        model = QuizRoom
        fields = (
            'id', 'code', 'quiz', 'quiz_title', 'host_username', 'status',
            'max_participants', 'current_question_index', 'participants',
            'participant_count', 'created_at', 'started_at'
        )

    def get_participant_count(self, obj):
        return obj.participants.count()
