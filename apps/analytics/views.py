from django.db.models import Avg, Sum, Count, ExpressionWrapper, FloatField, F
from django.utils import timezone
from datetime import timedelta
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import permissions

from apps.quizzes.models import QuizAttempt, Answer
from .models import TopicPerformance, DailyStats


class UserAnalyticsView(APIView):
    def get(self, request):
        user = request.user
        now = timezone.now()

        all_attempts = QuizAttempt.objects.filter(user=user, status='completed')

        avg_score = all_attempts.aggregate(avg=Avg('score'))['avg'] or 0
        total_time = all_attempts.aggregate(total=Sum('time_taken_seconds'))['total'] or 0

        # Sort topic performance in Python (accuracy is a property, not a DB field)
        topic_perf = list(TopicPerformance.objects.filter(user=user))
        topic_perf_sorted = sorted(topic_perf, key=lambda x: x.accuracy)

        weak_topics = [
            {'topic': tp.topic, 'accuracy': tp.accuracy, 'total': tp.total_questions}
            for tp in topic_perf_sorted[:5] if tp.total_questions >= 3
        ]
        strong_topics = [
            {'topic': tp.topic, 'accuracy': tp.accuracy, 'total': tp.total_questions}
            for tp in sorted(topic_perf, key=lambda x: x.accuracy, reverse=True)[:5]
            if tp.total_questions >= 3
        ]

        daily = DailyStats.objects.filter(
            user=user,
            date__gte=(now - timedelta(days=30)).date()
        ).order_by('date')

        daily_data = [
            {
                'date': str(d.date),
                'quizzes': d.quizzes_taken,
                'xp': d.xp_earned,
                'accuracy': round((d.correct_answers / d.questions_answered * 100), 1)
                    if d.questions_answered else 0,
            }
            for d in daily
        ]

        score_history = list(
            all_attempts.order_by('-started_at')[:10].values(
                'started_at', 'score', 'quiz__topic'
            )
        )
        score_history.reverse()

        answers = Answer.objects.filter(attempt__user=user)
        avg_time_per_q = answers.aggregate(avg=Avg('time_taken_seconds'))['avg'] or 0

        this_week = all_attempts.filter(started_at__gte=now - timedelta(days=7)).count()
        last_week = all_attempts.filter(
            started_at__gte=now - timedelta(days=14),
            started_at__lt=now - timedelta(days=7)
        ).count()

        return Response({
            'overview': {
                'total_quizzes': user.total_quizzes_taken,
                'overall_accuracy': user.accuracy,
                'average_score': round(avg_score, 1),
                'total_time_hours': round(total_time / 3600, 1),
                'current_streak': user.current_streak,
                'longest_streak': user.longest_streak,
                'xp': user.xp,
                'level': user.level,
                'this_week_quizzes': this_week,
                'last_week_quizzes': last_week,
                'avg_time_per_question': round(avg_time_per_q, 1),
            },
            'weak_topics': weak_topics,
            'strong_topics': strong_topics,
            'daily_activity': daily_data,
            'score_history': [
                {
                    'date': s['started_at'].strftime('%b %d'),
                    'score': s['score'],
                    'topic': s['quiz__topic'],
                }
                for s in score_history
            ],
        })


class TeacherAnalyticsView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    def get(self, request):
        if request.user.role not in ('teacher', 'admin'):
            return Response({'error': 'Forbidden'}, status=403)

        from apps.quizzes.models import Quiz
        teacher_quizzes = Quiz.objects.filter(creator=request.user)

        quiz_stats = []
        for quiz in teacher_quizzes.filter(status='ready')[:20]:
            attempts = QuizAttempt.objects.filter(quiz=quiz, status='completed')
            quiz_stats.append({
                'id': str(quiz.id),
                'title': quiz.title,
                'topic': quiz.topic,
                'play_count': quiz.play_count,
                'average_score': round(quiz.average_score, 1),
                'attempt_count': attempts.count(),
            })

        return Response({
            'total_quizzes_created': teacher_quizzes.count(),
            'total_attempts': QuizAttempt.objects.filter(
                quiz__creator=request.user, status='completed'
            ).count(),
            'quiz_stats': quiz_stats,
        })


class UpdateTopicPerformanceView(APIView):
    def post(self, request):
        attempt_id = request.data.get('attempt_id')
        try:
            attempt = QuizAttempt.objects.get(id=attempt_id, user=request.user, status='completed')
        except QuizAttempt.DoesNotExist:
            return Response({'error': 'Not found'}, status=404)

        answers = attempt.answers.select_related('question').all()
        topic_map = {}

        for answer in answers:
            topic = answer.question.topic_tag or attempt.quiz.topic
            if topic not in topic_map:
                topic_map[topic] = {'total': 0, 'correct': 0, 'time': 0}
            topic_map[topic]['total'] += 1
            if answer.is_correct:
                topic_map[topic]['correct'] += 1
            topic_map[topic]['time'] += answer.time_taken_seconds

        for topic, stats in topic_map.items():
            tp, created = TopicPerformance.objects.get_or_create(
                user=request.user, topic=topic
            )
            total = tp.total_questions + stats['total']
            tp.avg_time_seconds = (
                (tp.avg_time_seconds * tp.total_questions + stats['time']) / total
                if total > 0 else 0
            )
            tp.total_questions = total
            tp.correct_answers += stats['correct']
            tp.save()

        today = timezone.now().date()
        ds, _ = DailyStats.objects.get_or_create(user=request.user, date=today)
        ds.quizzes_taken += 1
        ds.questions_answered += attempt.total_questions
        ds.correct_answers += attempt.correct_count
        ds.xp_earned += attempt.xp_earned
        ds.time_spent_seconds += attempt.time_taken_seconds or 0
        ds.save()

        return Response({'status': 'updated'})