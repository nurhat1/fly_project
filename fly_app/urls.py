from django.urls import path

from . import views


urlpatterns = [
    path('', views.cheap_tickets_calendar, name='home'),
    path('booking_flight/', views.booking_flight, name='booking_flight'),
]
