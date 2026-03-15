"""
WebSocket consumer for real-time multiplayer quiz rooms.
Handles: join, answer submission, live leaderboard updates, host control.
"""
import json
from channels.generic.websocket import AsyncWebsocketConsumer
from channels.db import database_sync_to_async
from django.utils import timezone


class QuizRoomConsumer(AsyncWebsocketConsumer):
    async def connect(self):
        self.room_id = self.scope['url_route']['kwargs']['room_id']
        self.room_group = f'quiz_room_{self.room_id}'
        self.user = self.scope['user']

        if not self.user.is_authenticated:
            await self.close()
            return

        await self.channel_layer.group_add(self.room_group, self.channel_name)
        await self.accept()

        # Notify others of join
        await self.channel_layer.group_send(self.room_group, {
            'type': 'user_joined',
            'username': self.user.username,
            'user_id': self.user.id,
        })

        # Send current room state to this user
        room_data = await self.get_room_state()
        await self.send(text_data=json.dumps({'type': 'room_state', 'data': room_data}))

    async def disconnect(self, close_code):
        await self.channel_layer.group_discard(self.room_group, self.channel_name)
        await self.channel_layer.group_send(self.room_group, {
            'type': 'user_left',
            'username': self.user.username,
        })

    async def receive(self, text_data):
        data = json.loads(text_data)
        msg_type = data.get('type')

        if msg_type == 'start_quiz':
            await self.handle_start(data)
        elif msg_type == 'submit_answer':
            await self.handle_answer(data)
        elif msg_type == 'next_question':
            await self.handle_next_question(data)
        elif msg_type == 'end_quiz':
            await self.handle_end(data)

    async def handle_start(self, data):
        """Host starts the quiz."""
        is_host = await self.is_room_host()
        if not is_host:
            return

        await self.update_room_status('in_progress')
        await self.channel_layer.group_send(self.room_group, {
            'type': 'quiz_started',
            'question_index': 0,
        })

    async def handle_answer(self, data):
        """Participant submits an answer."""
        question_id = data.get('question_id')
        option_ids = data.get('option_ids', [])

        is_correct, points = await self.process_answer(question_id, option_ids)
        await self.update_participant_score(points)
        leaderboard = await self.get_leaderboard()

        await self.channel_layer.group_send(self.room_group, {
            'type': 'leaderboard_update',
            'leaderboard': leaderboard,
            'answer_event': {
                'username': self.user.username,
                'is_correct': is_correct,
            }
        })

    async def handle_next_question(self, data):
        """Host advances to next question."""
        is_host = await self.is_room_host()
        if not is_host:
            return

        new_index = await self.increment_question_index()
        await self.channel_layer.group_send(self.room_group, {
            'type': 'next_question',
            'question_index': new_index,
        })

    async def handle_end(self, data):
        """Host ends the quiz."""
        is_host = await self.is_room_host()
        if not is_host:
            return

        await self.update_room_status('finished')
        leaderboard = await self.get_leaderboard()
        await self.channel_layer.group_send(self.room_group, {
            'type': 'quiz_ended',
            'leaderboard': leaderboard,
        })

    # ── Channel layer event handlers (broadcast → individual send) ───────────

    async def user_joined(self, event):
        await self.send(text_data=json.dumps(event))

    async def user_left(self, event):
        await self.send(text_data=json.dumps(event))

    async def quiz_started(self, event):
        await self.send(text_data=json.dumps(event))

    async def leaderboard_update(self, event):
        await self.send(text_data=json.dumps(event))

    async def next_question(self, event):
        await self.send(text_data=json.dumps(event))

    async def quiz_ended(self, event):
        await self.send(text_data=json.dumps(event))

    # ── DB helpers ────────────────────────────────────────────────────────────

    @database_sync_to_async
    def get_room_state(self):
        from .models import QuizRoom, RoomParticipant
        try:
            room = QuizRoom.objects.select_related('quiz', 'host').get(id=self.room_id)
            participants = RoomParticipant.objects.filter(room=room).select_related('user')
            return {
                'id': str(room.id),
                'code': room.code,
                'status': room.status,
                'quiz_title': room.quiz.title,
                'current_question_index': room.current_question_index,
                'participants': [
                    {'username': p.user.username, 'score': p.score}
                    for p in participants
                ],
            }
        except Exception:
            return {}

    @database_sync_to_async
    def is_room_host(self):
        from .models import QuizRoom
        try:
            room = QuizRoom.objects.get(id=self.room_id)
            return room.host_id == self.user.id
        except Exception:
            return False

    @database_sync_to_async
    def update_room_status(self, new_status):
        from .models import QuizRoom
        QuizRoom.objects.filter(id=self.room_id).update(
            status=new_status,
            started_at=timezone.now() if new_status == 'in_progress' else None,
            finished_at=timezone.now() if new_status == 'finished' else None,
        )

    @database_sync_to_async
    def increment_question_index(self):
        from .models import QuizRoom
        room = QuizRoom.objects.get(id=self.room_id)
        room.current_question_index += 1
        room.save(update_fields=['current_question_index'])
        return room.current_question_index

    @database_sync_to_async
    def process_answer(self, question_id, option_ids):
        from .models import Question, Option
        try:
            question = Question.objects.get(id=question_id)
            correct_ids = set(str(o.id) for o in question.options.filter(is_correct=True))
            selected_ids = set(str(i) for i in option_ids)
            is_correct = correct_ids == selected_ids
            return is_correct, 10 if is_correct else 0
        except Exception:
            return False, 0

    @database_sync_to_async
    def update_participant_score(self, points):
        from .models import RoomParticipant
        RoomParticipant.objects.filter(
            room_id=self.room_id, user=self.user
        ).update(
            score=RoomParticipant.objects.get(room_id=self.room_id, user=self.user).score + points,
            answers_given=RoomParticipant.objects.get(room_id=self.room_id, user=self.user).answers_given + 1,
        )

    @database_sync_to_async
    def get_leaderboard(self):
        from .models import RoomParticipant
        participants = RoomParticipant.objects.filter(
            room_id=self.room_id
        ).select_related('user').order_by('-score')
        return [
            {'username': p.user.username, 'score': p.score, 'answers_given': p.answers_given}
            for p in participants
        ]
