from django.urls import path
from .views import (
    TopicViewSet,
    HealthView,
    StatsView,
    ShutdownView
)

urlpatterns = [
    path('topics/', TopicViewSet.as_view(), name='topics'),
    path('topics/<str:topic_name>/', TopicViewSet.as_view(), name='topic_detail'),
    path('health/', HealthView.as_view(), name='health'),
    path('stats/', StatsView.as_view(), name='stats'),
    path('shutdown/', ShutdownView.as_view(), name='shutdown'),
]
