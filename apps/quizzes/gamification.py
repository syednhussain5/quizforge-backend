"""
Gamification engine: awards XP, badges, and sends notifications.
Called after quiz completion to process rewards.
"""
from django.conf import settings
from apps.users.models import Badge, UserBadge, Notification


def process_quiz_completion(user, attempt):
    """
    Main entry point: award XP, update stats, check badges, update streak.
    Returns dict with earned rewards for the client to display.
    """
    rewards = {
        'xp_earned': 0,
        'new_badges': [],
        'level_up': False,
        'old_level': user.level,
        'streak_updated': False,
    }

    # 1. Calculate XP
    xp = _calculate_xp(attempt)
    attempt.xp_earned = xp
    attempt.save(update_fields=['xp_earned'])

    # 2. Update user stats
    user.total_quizzes_taken += 1
    user.total_correct_answers += attempt.correct_count
    user.total_questions_answered += attempt.total_questions
    user.save(update_fields=['total_quizzes_taken', 'total_correct_answers', 'total_questions_answered'])

    # 3. Add XP (may level up)
    old_level = user.level
    user.add_xp(xp)
    rewards['xp_earned'] = xp
    if user.level > old_level:
        rewards['level_up'] = True
        rewards['new_level'] = user.level
        _notify(user, 'level_up', f'Level {user.level}!', f'You reached level {user.level}! 🎉')

    # 4. Update streak
    user.update_streak()
    rewards['streak_updated'] = True
    rewards['current_streak'] = user.current_streak

    # 5. Check and award badges
    new_badges = _check_badges(user)
    rewards['new_badges'] = new_badges

    # 6. Update quiz stats
    attempt.quiz.update_stats(attempt.score)

    return rewards


def _calculate_xp(attempt):
    """XP formula based on score, difficulty, time, and streak bonus."""
    base = attempt.correct_count * settings.XP_PER_CORRECT_ANSWER
    completion_bonus = settings.XP_PER_QUIZ_COMPLETION

    # Difficulty multiplier
    difficulty_mult = {'easy': 1.0, 'medium': 1.3, 'hard': 1.6, 'adaptive': 1.4}
    mult = difficulty_mult.get(attempt.quiz.difficulty, 1.0)

    # Speed bonus: if timed quiz and completed fast
    speed_bonus = 0
    if attempt.quiz.time_limit_minutes and attempt.time_taken_seconds:
        time_limit_s = attempt.quiz.time_limit_minutes * 60
        if attempt.time_taken_seconds < time_limit_s * 0.6:
            speed_bonus = 25

    return int((base + completion_bonus + speed_bonus) * mult)


def _check_badges(user):
    """Check if user has earned any new badges and award them."""
    new_badges = []
    all_badges = Badge.objects.all()
    earned_ids = set(UserBadge.objects.filter(user=user).values_list('badge_id', flat=True))

    for badge in all_badges:
        if badge.id in earned_ids:
            continue

        earned = False
        if badge.badge_type == 'quiz_count' and user.total_quizzes_taken >= badge.threshold:
            earned = True
        elif badge.badge_type == 'xp' and user.xp >= badge.threshold:
            earned = True
        elif badge.badge_type == 'streak' and user.current_streak >= badge.threshold:
            earned = True
        elif badge.badge_type == 'accuracy':
            if user.total_questions_answered >= 20 and user.accuracy >= badge.threshold:
                earned = True

        if earned:
            UserBadge.objects.create(user=user, badge=badge)
            user.add_xp(badge.xp_reward)
            new_badges.append({'name': badge.name, 'icon': badge.icon, 'description': badge.description})
            _notify(
                user, 'badge_earned',
                f'Badge Earned: {badge.name}',
                f'{badge.icon} You earned the "{badge.name}" badge!'
            )

    return new_badges


def _notify(user, notif_type, title, message, data=None):
    Notification.objects.create(
        user=user,
        notif_type=notif_type,
        title=title,
        message=message,
        data=data or {}
    )
