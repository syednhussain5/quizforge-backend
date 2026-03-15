import random
import string
from django.utils import timezone
from django.db.models import Q
from rest_framework import generics, permissions, status
from rest_framework.response import Response
from rest_framework.views import APIView
from rest_framework.parsers import MultiPartParser, FormParser

from .models import Quiz, Question, Option, QuizAttempt, Answer, QuizRoom, RoomParticipant
from .serializers import (
    QuizListSerializer, QuizDetailSerializer, QuizCreateSerializer,
    QuizAttemptListSerializer, QuizAttemptDetailSerializer,
    SubmitAnswerSerializer, CompleteAttemptSerializer,
    QuizRoomSerializer
)
from .gamification import process_quiz_completion
from .tasks import generate_quiz_task


class QuizListCreateView(generics.ListCreateAPIView):
    """List public quizzes or create a new one (triggers AI generation)."""

    def get_serializer_class(self):
        if self.request.method == 'POST':
            return QuizCreateSerializer
        return QuizListSerializer

    def get_queryset(self):
        qs = Quiz.objects.filter(status='ready')
        q = self.request.query_params.get('q')
        difficulty = self.request.query_params.get('difficulty')
        my = self.request.query_params.get('my')

        if my == 'true':
            qs = Quiz.objects.filter(creator=self.request.user)
        else:
            qs = qs.filter(is_public=True)

        if q:
            qs = qs.filter(Q(title__icontains=q) | Q(topic__icontains=q))
        if difficulty:
            qs = qs.filter(difficulty=difficulty)

        return qs.order_by('-created_at')

    def create(self, request, *args, **kwargs):
        serializer = QuizCreateSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        quiz = serializer.save(creator=request.user, status='generating')

        # Kick off async AI generation
        generate_quiz_task(str(quiz.id))

        return Response(
            QuizListSerializer(quiz).data,
            status=status.HTTP_201_CREATED
        )


class QuizDetailView(generics.RetrieveUpdateDestroyAPIView):
    queryset = Quiz.objects.all()
    lookup_field = 'id'

    def get_serializer_class(self):
        if self.request.method in ('PUT', 'PATCH'):
            return QuizCreateSerializer
        return QuizDetailSerializer

    def get_permissions(self):
        if self.request.method in ('PUT', 'PATCH', 'DELETE'):
            return [permissions.IsAuthenticated()]
        return [permissions.IsAuthenticatedOrReadOnly()]

    def check_object_permissions(self, request, obj):
        if request.method in ('PUT', 'PATCH', 'DELETE'):
            if obj.creator != request.user and not request.user.is_staff:
                self.permission_denied(request)
        super().check_object_permissions(request, obj)


class QuizStatusView(APIView):
    """Poll this to check if AI generation is complete."""

    def get(self, request, id):
        try:
            quiz = Quiz.objects.get(id=id)
        except Quiz.DoesNotExist:
            return Response({'error': 'Not found'}, status=404)

        return Response({
            'id': str(quiz.id),
            'status': quiz.status,
            'question_count': quiz.questions.count(),
        })


class StartAttemptView(APIView):
    """Start a new quiz attempt. Returns attempt ID and questions."""

    def post(self, request, quiz_id):
        try:
            quiz = Quiz.objects.prefetch_related('questions__options').get(id=quiz_id, status='ready')
        except Quiz.DoesNotExist:
            return Response({'error': 'Quiz not found or not ready'}, status=404)

        # Create attempt
        attempt = QuizAttempt.objects.create(
            user=request.user,
            quiz=quiz,
            total_questions=quiz.questions.count(),
            is_adaptive=quiz.difficulty == 'adaptive',
        )

        # Build shuffled question order
        questions = list(quiz.questions.values_list('id', flat=True))
        if quiz.randomize_questions:
            random.shuffle(questions)
        attempt.question_order = [str(q) for q in questions]
        attempt.save(update_fields=['question_order'])

        quiz_data = QuizDetailSerializer(quiz, context={'request': request}).data
        return Response({
            'attempt_id': str(attempt.id),
            'quiz': quiz_data,
            'time_limit_minutes': quiz.time_limit_minutes,
        })


class SubmitAnswerView(APIView):
    """Submit an answer for one question during an attempt."""

    def post(self, request, attempt_id):
        try:
            attempt = QuizAttempt.objects.get(id=attempt_id, user=request.user, status='in_progress')
        except QuizAttempt.DoesNotExist:
            return Response({'error': 'Attempt not found or already completed'}, status=404)

        serializer = SubmitAnswerSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        data = serializer.validated_data

        # Prevent re-answering the same question
        if attempt.answers.filter(question_id=data['question_id']).exists():
            return Response({'error': 'Already answered this question'}, status=400)

        try:
            question = Question.objects.get(id=data['question_id'], quiz=attempt.quiz)
        except Question.DoesNotExist:
            return Response({'error': 'Question not found'}, status=404)

        selected_options = Option.objects.filter(
            id__in=data['selected_option_ids'],
            question=question
        )
        correct_options = question.options.filter(is_correct=True)
        is_correct = (
            set(selected_options.values_list('id', flat=True)) ==
            set(correct_options.values_list('id', flat=True))
        )

        answer = Answer.objects.create(
            attempt=attempt,
            question=question,
            is_correct=is_correct,
            time_taken_seconds=data['time_taken_seconds'],
            shown_difficulty=question.difficulty,
        )
        answer.selected_options.set(selected_options)

        if is_correct:
            attempt.correct_count += 1
            attempt.save(update_fields=['correct_count'])

        return Response({
            'is_correct': is_correct,
            'correct_option_ids': list(correct_options.values_list('id', flat=True)),
            'explanation': question.explanation if attempt.quiz.allow_review else '',
        })


class CompleteAttemptView(APIView):
    """Mark an attempt as completed and calculate final score + rewards."""

    def post(self, request, attempt_id):
        try:
            attempt = QuizAttempt.objects.select_related('quiz', 'user').get(
                id=attempt_id, user=request.user, status='in_progress'
            )
        except QuizAttempt.DoesNotExist:
            return Response({'error': 'Attempt not found'}, status=404)

        serializer = CompleteAttemptSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        data = serializer.validated_data

        attempt.status = 'completed'
        attempt.time_taken_seconds = data['time_taken_seconds']
        attempt.tab_switches = data.get('tab_switches', 0)
        attempt.completed_at = timezone.now()

        if attempt.total_questions > 0:
            attempt.score = round((attempt.correct_count / attempt.total_questions) * 100, 1)

        attempt.save()

        # Award XP, badges, streaks
        rewards = process_quiz_completion(request.user, attempt)

        # Build weak topics for smart revision hint
        wrong_answers = attempt.answers.filter(is_correct=False).select_related('question')
        weak_topics = list(set(a.question.topic_tag for a in wrong_answers if a.question.topic_tag))

        return Response({
            'attempt_id': str(attempt.id),
            'score': attempt.score,
            'correct_count': attempt.correct_count,
            'total_questions': attempt.total_questions,
            'time_taken_seconds': attempt.time_taken_seconds,
            'tab_switches': attempt.tab_switches,
            'rewards': rewards,
            'weak_topics': weak_topics,
        })


class AttemptDetailView(generics.RetrieveAPIView):
    """Get full attempt details with answers (for review)."""
    serializer_class = QuizAttemptDetailSerializer

    def get_queryset(self):
        return QuizAttempt.objects.filter(user=self.request.user)

    def get_object(self):
        attempt = super().get_object()
        if attempt.status != 'completed':
            from rest_framework.exceptions import PermissionDenied
            raise PermissionDenied("Attempt not completed yet")
        return attempt


class UserAttemptsView(generics.ListAPIView):
    """List all past attempts for the current user."""
    serializer_class = QuizAttemptListSerializer

    def get_queryset(self):
        return QuizAttempt.objects.filter(
            user=self.request.user
        ).select_related('quiz').order_by('-started_at')


class SmartRevisionView(APIView):
    """Generate a revision quiz from user's worst-performing topics."""

    def post(self, request):
        from .ai_service import generate_revision_quiz
        from .models import Question, Option

        # Get recently wrong answers
        wrong_answers = Answer.objects.filter(
            attempt__user=request.user,
            is_correct=False,
        ).select_related('question').order_by('-answered_at')[:20]

        if not wrong_answers:
            return Response({'error': 'No wrong answers found to revise'}, status=400)

        wrong_data = [
            {
                'question_text': a.question.text,
                'correct_answer': a.question.options.filter(is_correct=True).first().text
                    if a.question.options.filter(is_correct=True).exists() else '',
                'topic_tag': a.question.topic_tag,
            }
            for a in wrong_answers[:10]
        ]

        # Determine dominant topic
        topics = [a.question.topic_tag or a.question.quiz.topic for a in wrong_answers[:10]]
        main_topic = max(set(topics), key=topics.count) if topics else 'General'

        raw_questions = generate_revision_quiz(wrong_data)

        # Create a revision quiz
        quiz = Quiz.objects.create(
            creator=request.user,
            title=f"Smart Revision: {main_topic}",
            topic=main_topic,
            difficulty='medium',
            question_count=len(raw_questions),
            is_public=False,
            is_ai_generated=True,
            status='ready',
        )

        for idx, q_data in enumerate(raw_questions):
            question = Question.objects.create(
                quiz=quiz,
                text=q_data.get('text', ''),
                question_type=q_data.get('question_type', 'mcq'),
                difficulty='easy',
                explanation=q_data.get('explanation', ''),
                topic_tag=q_data.get('topic_tag', main_topic),
                order=idx,
            )
            for opt_idx, opt_data in enumerate(q_data.get('options', [])):
                Option.objects.create(
                    question=question,
                    text=opt_data.get('text', ''),
                    is_correct=opt_data.get('is_correct', False),
                    order=opt_idx,
                )

        return Response(QuizListSerializer(quiz).data, status=201)


# ─── Multiplayer ─────────────────────────────────────────────────────────────

class CreateRoomView(APIView):
    """Create a multiplayer room."""

    def post(self, request):
        quiz_id = request.data.get('quiz_id')
        try:
            quiz = Quiz.objects.get(id=quiz_id, status='ready')
        except Quiz.DoesNotExist:
            return Response({'error': 'Quiz not found'}, status=404)

        code = ''.join(random.choices(string.ascii_uppercase + string.digits, k=6))
        room = QuizRoom.objects.create(
            code=code,
            quiz=quiz,
            host=request.user,
            max_participants=request.data.get('max_participants', 10),
        )
        RoomParticipant.objects.create(room=room, user=request.user)
        return Response(QuizRoomSerializer(room).data, status=201)


class JoinRoomView(APIView):
    """Join a multiplayer room by code."""

    def post(self, request):
        code = request.data.get('code', '').upper()
        try:
            room = QuizRoom.objects.get(code=code, status='waiting')
        except QuizRoom.DoesNotExist:
            return Response({'error': 'Room not found or already started'}, status=404)

        if room.participants.count() >= room.max_participants:
            return Response({'error': 'Room is full'}, status=400)

        RoomParticipant.objects.get_or_create(room=room, user=request.user)
        return Response(QuizRoomSerializer(room).data)


class RoomDetailView(generics.RetrieveAPIView):
    serializer_class = QuizRoomSerializer
    queryset = QuizRoom.objects.all()
    lookup_field = 'id'
