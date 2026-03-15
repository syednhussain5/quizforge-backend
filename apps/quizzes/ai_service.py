import json
import logging
import re
import requests
from django.conf import settings

logger = logging.getLogger(__name__)


def call_openrouter(prompt: str) -> str:
    """Call OpenRouter API with free model."""
    api_key = getattr(settings, 'OPENROUTER_API_KEY', '')
    if not api_key:
        logger.error("OPENROUTER_API_KEY not set")
        return ""

    try:
        response = requests.post(
            "https://openrouter.ai/api/v1/chat/completions",
            headers={
                "Authorization": f"Bearer {api_key}",
                "Content-Type": "application/json",
                "HTTP-Referer": "http://localhost:3000",
                "X-Title": "QuizForge",
            },
            json={
                "model": "google/gemma-3-4b-it:free",
                "messages": [
                    {"role": "user", "content": prompt}
                ],
                "temperature": 0.7,
                "max_tokens": 4000,
            },
            timeout=60,
        )
        data = response.json()
        return data["choices"][0]["message"]["content"]
    except Exception as e:
        logger.error(f"OpenRouter error: {e}")
        return ""


def parse_json_response(text: str):
    if not text:
        return None
    text = re.sub(r"```json", "", text)
    text = re.sub(r"```", "", text)
    text = text.strip()
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        match = re.search(r'(\[.*\]|\{.*\})', text, re.DOTALL)
        if match:
            try:
                return json.loads(match.group(1))
            except json.JSONDecodeError:
                pass
    logger.error(f"Failed to parse JSON: {text[:200]}")
    return None


QUESTION_SCHEMA = """
Return ONLY a valid JSON array with no explanation or markdown.
Each object must follow this exact schema:
{
  "text": "Question text here",
  "question_type": "mcq",
  "difficulty": "easy" | "medium" | "hard",
  "explanation": "Brief explanation of correct answer",
  "topic_tag": "sub-topic name",
  "options": [
    {"text": "Option A", "is_correct": false},
    {"text": "Option B", "is_correct": true},
    {"text": "Option C", "is_correct": false},
    {"text": "Option D", "is_correct": false}
  ]
}
Rules:
- mcq must have exactly 4 options, exactly 1 correct
- true_false must have exactly 2 options (True/False)
- Return only the JSON array, nothing else
"""


def _fallback_questions(topic: str, count: int):
    return [
        {
            "text": f"What is an important concept in {topic}?",
            "question_type": "mcq",
            "difficulty": "medium",
            "explanation": "Fallback question — AI unavailable.",
            "topic_tag": topic,
            "options": [
                {"text": "Concept A", "is_correct": True},
                {"text": "Concept B", "is_correct": False},
                {"text": "Concept C", "is_correct": False},
                {"text": "Concept D", "is_correct": False},
            ]
        }
    ] * count


def generate_quiz_questions(topic: str, count: int, difficulty: str, source_material: str = "") -> list:
    if source_material:
        prompt = f"""Create {count} quiz questions about "{topic}" based on this material:

{source_material[:6000]}

Difficulty: {difficulty}

{QUESTION_SCHEMA}"""
    else:
        prompt = f"""Create {count} quiz questions about "{topic}".

Difficulty: {difficulty}
Mix of MCQ and True/False questions. Questions must be factually accurate.

{QUESTION_SCHEMA}"""

    text = call_openrouter(prompt)
    questions = parse_json_response(text)

    if isinstance(questions, list) and len(questions) > 0:
        return questions[:count]

    return _fallback_questions(topic, count)


def generate_adaptive_question(topic, current_difficulty, previous_questions, user_accuracy):
    if user_accuracy >= 80:
        difficulty = "hard"
    elif user_accuracy >= 50:
        difficulty = "medium"
    else:
        difficulty = "easy"

    avoid_text = "\n".join(previous_questions[:5]) if previous_questions else "none"

    prompt = f"""Generate 1 quiz question about "{topic}".
Difficulty: {difficulty}
Avoid similar to: {avoid_text}

{QUESTION_SCHEMA}
Return JSON array with exactly 1 question."""

    text = call_openrouter(prompt)
    questions = parse_json_response(text)

    if isinstance(questions, list) and questions:
        q = questions[0]
        q["difficulty"] = difficulty
        return q

    return _fallback_questions(topic, 1)[0]


def generate_revision_quiz(wrong_answers: list) -> list:
    context = json.dumps(wrong_answers[:10], indent=2)

    prompt = f"""A student got these questions wrong:
{context}

Generate {min(len(wrong_answers), 5)} revision questions on the same concepts.
Difficulty: easy to medium.

{QUESTION_SCHEMA}"""

    text = call_openrouter(prompt)
    questions = parse_json_response(text)

    if isinstance(questions, list):
        return questions

    return []