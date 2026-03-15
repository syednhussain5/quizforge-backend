from django.utils import timezone
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import generics
from apps.quizzes.serializers import QuizListSerializer
from .models import DailyChallenge, DailyChallengeAttempt


class TodayChallengeView(APIView):
    def get(self, request):
        today = timezone.now().date()
        try:
            challenge = DailyChallenge.objects.select_related('quiz').get(date=today)
        except DailyChallenge.DoesNotExist:
            return Response({'message': 'No challenge today yet. Check back soon!'}, status=404)

        completed = DailyChallengeAttempt.objects.filter(
            challenge=challenge, user=request.user
        ).exists()

        # Leaderboard for today
        leaderboard = DailyChallengeAttempt.objects.filter(
            challenge=challenge
        ).select_related('user').order_by('-score', 'completed_at')[:20]

        return Response({
            'challenge': {
                'id': challenge.id,
                'date': str(challenge.date),
                'quiz': QuizListSerializer(challenge.quiz).data,
                'completed_by_user': completed,
                'total_participants': challenge.participants.count(),
            },
            'leaderboard': [
                {
                    'rank': idx + 1,
                    'username': a.user.username,
                    'score': a.score,
                    'xp_earned': a.xp_earned,
                }
                for idx, a in enumerate(leaderboard)
            ]
        })
