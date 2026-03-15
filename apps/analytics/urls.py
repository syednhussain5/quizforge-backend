from django.urls import path
from . import views

urlpatterns = [
    path('me/', views.UserAnalyticsView.as_view(), name='user-analytics'),
    path('teacher/', views.TeacherAnalyticsView.as_view(), name='teacher-analytics'),
    path('update/', views.UpdateTopicPerformanceView.as_view(), name='update-analytics'),
]
