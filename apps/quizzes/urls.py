from django.urls import path
from . import views

urlpatterns = [
    # Quizzes
    path('', views.QuizListCreateView.as_view(), name='quiz-list-create'),
    path('<uuid:id>/', views.QuizDetailView.as_view(), name='quiz-detail'),
    path('<uuid:id>/status/', views.QuizStatusView.as_view(), name='quiz-status'),

    # Attempts
    path('<uuid:quiz_id>/start/', views.StartAttemptView.as_view(), name='start-attempt'),
    path('attempts/', views.UserAttemptsView.as_view(), name='user-attempts'),
    path('attempts/<uuid:pk>/', views.AttemptDetailView.as_view(), name='attempt-detail'),
    path('attempts/<uuid:attempt_id>/answer/', views.SubmitAnswerView.as_view(), name='submit-answer'),
    path('attempts/<uuid:attempt_id>/complete/', views.CompleteAttemptView.as_view(), name='complete-attempt'),

    # Smart Revision
    path('revision/', views.SmartRevisionView.as_view(), name='smart-revision'),

    # Multiplayer
    path('rooms/create/', views.CreateRoomView.as_view(), name='create-room'),
    path('rooms/join/', views.JoinRoomView.as_view(), name='join-room'),
    path('rooms/<uuid:id>/', views.RoomDetailView.as_view(), name='room-detail'),
]
