from django.urls import path

from . import views


urlpatterns = [
    path('', views.cheap_tickets_calendar, name='home'),
]
