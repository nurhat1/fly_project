from django.shortcuts import render
from django.conf import settings
from django.contrib import messages

import time
from redis import Redis
import pickle
import sys
import requests
import datetime

# Create your views here.


redis_cli = Redis(host=settings.REDIS_HOST, port=settings.REDIS_PORT)

DIRS = ['ALA-TSE', 'TSE-ALA', 'ALA-MOW', 'MOW-ALA', 'ALA-CIT', 'CIT-ALA', 'TSE-MOW', 'MOW-TSE', 'TSE-LED', 'LED-TSE']
DIRECTIONS = ['ALA', 'TSE', 'MOW', 'CIT', 'LED']

HEADERS = {
    'Content-Type': 'application/json'
}


def cheap_tickets_calendar(request):
    """ Веб-сервис, который выводит самые дешевые билеты за текущий месяц по заданному направлению """

    # dictionary that will have all necessary data to show to the users
    new_ticket_data, min_price, fly_from, fly_to = (None, None, None, None)

    if request.GET.get("fly_from") and request.GET.get("fly_to"):

        # get user inputs
        fly_from = request.GET.get("fly_from")
        fly_to = request.GET.get("fly_to")
        print(f"fly_from: {fly_from} // fly_to: {fly_to}")

        direction = f"{fly_from}-{fly_to}"
        if direction in DIRS:
            # get data from Redis cache
            try:
                dir_data = pickle.loads(redis_cli.get(direction))
                new_ticket_data = dir_data["ticket_data"]
                min_price = dir_data["min_price"]
                print("----------- SUCCESS READ FROM REDIS -----------")
                print(f"min_price: {min_price}")
            except:
                err = sys.exc_info()
                print(f"Error occurs when get tickets data from redis! {err[-1].tb_lineno, err}")
                messages.warning(request, 'Can not find tickets. Please try later.')
        else:
            messages.warning(request, 'Please choose valid direction.')

    context = {
        'directions': DIRECTIONS,
        'fly_from': fly_from,
        'fly_to': fly_to,
        'new_ticket_data': new_ticket_data,
        'min_price': min_price
    }

    return render(request, 'fly_app/index.html', context)


def booking_flight(request):
    """ Веб-сервис, который проверяет валидность билета по booking_token """

    if request.method == 'POST':
        # get booking_token
        bt = request.POST.get("booking_token")

        # init booking data dictionary
        bd = {}

        # check founded ticket for validation
        while True:
            cr = requests.get(
                f"{settings.BASE_URL}/api/v0.1/check_flights?v=2&booking_token={bt}&bnum=0&pnum=1&"
                f"affily={settings.PARTNER}&currency=EUR&adults=1&children=0&infants=0")
            rd = cr.json()

            if rd["flights_checked"]:
                if rd["flights_invalid"]:
                    print(f"Flight is invalid. flights_invalid: {rd['flights_invalid']}")
                else:
                    bd["airline"] = rd["flights"][0]["airline"]["Name"]
                    bd["dep_time"] = datetime.datetime.fromtimestamp(rd["flights"][0]["dtime"]) \
                        .strftime('%d-%m-%Y %H:%M:%S')
                    bd["arr_time"] = datetime.datetime.fromtimestamp(rd["flights"][0]["atime"]) \
                        .strftime('%d-%m-%Y %H:%M:%S')
                    bd["duration"] = datetime.datetime.fromtimestamp(rd["flights"][0]["atime"]) - datetime.datetime. \
                        fromtimestamp(rd["flights"][0]["dtime"])
                    bd["total"] = rd["total"]
                    bd["price_change"] = rd["price_change"]
                break
            time.sleep(30)

        context = {
            "bd": bd
        }
        return render(request, 'fly_app/booking.html', context)
