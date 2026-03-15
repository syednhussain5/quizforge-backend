from django.urls import path
from . import views

urlpatterns = [
    path('today/', views.TodayChallengeView.as_view(), name='today-challenge'),
]
