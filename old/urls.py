from django.urls import path
from . import views
from .views import send_telegram_message



urlpatterns = [
    path('', views.index, name='home'),
    path('send_telegram_message/', views.send_telegram_message, name='send_telegram_message'),
]