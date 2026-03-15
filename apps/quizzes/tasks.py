import logging
from django.utils import timezone

logger = logging.getLogger(__name__)


def generate_quiz_task(quiz_id: str):
    """Generate questions for a quiz using AI."""
    from .models import Quiz, Question, Option
    from .ai_service import generate_quiz_questions

    try:
        quiz = Quiz.objects.get(id=quiz_id)
        logger.info(f"Generating questions for quiz {quiz_id}")

        raw_questions = generate_quiz_questions(
            topic=quiz.topic,
            count=quiz.question_count,
            difficulty=quiz.difficulty,
            source_material=quiz.source_material,
        )

        if not raw_questions:
            raise ValueError("AI returned no questions")

        for idx, q_data in enumerate(raw_questions):
            question = Question.objects.create(
                quiz=quiz,
                text=q_data.get('text', ''),
                question_type=q_data.get('question_type', 'mcq'),
                difficulty=q_data.get('difficulty', 'medium'),
                explanation=q_data.get('explanation', ''),
                topic_tag=q_data.get('topic_tag', quiz.topic),
                order=idx,
            )
            for opt_idx, opt_data in enumerate(q_data.get('options', [])):
                Option.objects.create(
                    question=question,
                    text=opt_data.get('text', ''),
                    is_correct=opt_data.get('is_correct', False),
                    order=opt_idx,
                )

        quiz.status = 'ready'
        quiz.save(update_fields=['status'])
        logger.info(f"Quiz {quiz_id} ready with {len(raw_questions)} questions")

    except Exception as exc:
        logger.error(f"Quiz generation failed: {exc}")
        try:
            quiz = Quiz.objects.get(id=quiz_id)
            quiz.status = 'failed'
            quiz.save(update_fields=['status'])
        except Exception:
            pass
