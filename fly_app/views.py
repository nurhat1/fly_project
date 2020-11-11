from django.shortcuts import render
from django.conf import settings
from django.views.decorators.cache import cache_page

import datetime
import requests
import pprint
import time

# Create your views here.


DIRECTIONS = ['ALA', 'TSE', 'MOW', 'CIT', 'LED']

HEADERS = {
    'Content-Type': 'application/json'
}


def check_booking(booking_token, adults, children, infants):
    """ function that make request to check_flights and return answer of service """
    pnum = adults + children + infants

    r = requests.get(f'{settings.BASE_URL}/api/v0.1/check_flights?v=2&booking_token={booking_token}&bnum={pnum}&'
                     f'pnum={pnum}&affily={settings.PARTNER}_kz&currency=KZT&adults={adults}&children={children}&'
                     f'infants={infants}').json()

    answer = r['flights_invalid']

    if not answer:
        answer = 'Available'
    else:
        answer = 'Not available'

    return answer


@cache_page(60 * 5)
def home(request):
    """ home view """
    directions_table = []
    found_ticket = None
    answer = None

    # init current day and second date with a difference of 30 days
    date_from = datetime.date.today().strftime('%d/%m/%Y')
    date_to = (datetime.date.today() + datetime.timedelta(days=30)).strftime('%d/%m/%Y')

    # get prices for all 10 directions
    for direction in DIRECTIONS:
        # get fly_from and fly_to from direction string
        fly_from = direction.split(' - ')[0]
        fly_to = direction.split(' - ')[1]

        # make GET request with params
        r = requests.get(f'{settings.BASE_URL}/flights?fly_from={fly_from}&fly_to={fly_to}&date_from={date_from}'
                         f'&date_to={date_to}&adults=1&partner={settings.PARTNER}&curr=KZT', headers=HEADERS)

        # get data from response
        direction_data = r.json()['data']

        # init min_price and its booking_token for all 10 directions
        min_price = direction_data[0]['price']
        booking_token = ''
        for i in range(len(direction_data)):
            if direction_data[i]['price'] < min_price:
                min_price = direction_data[i]['price']
                booking_token = direction_data[i]['booking_token']

        # add direction, min_price and booking_token to directions_table
        directions_table.append({
            'direction': direction,
            'price': min_price,
            'booking_token': booking_token
        })

    if request.method == 'POST':
        # get the user inputs
        direction = request.POST.get('direction')
        fly_from = direction.split(' - ')[0]
        fly_to = direction.split(' - ')[1]
        adults_count = int(request.POST.get('adults_count'))
        children_count = int(request.POST.get('children_count'))
        infants_count = int(request.POST.get('infants_count'))

        # get tickets price
        r = requests.get(f'{settings.BASE_URL}/flights?fly_from={fly_from}&fly_to={fly_to}&date_from={date_from}'
                         f'&date_to={date_to}&adults={adults_count}&children={children_count}&infants={infants_count}'
                         f'&partner={settings.PARTNER}&curr=KZT', headers=HEADERS)

        # get data
        datas = r.json()['data']

        # find minimal price from data
        _min = datas[0]['price']
        _min_index = 0
        for i in range(len(datas)):
            # print(datas[i]['price'])
            if datas[i]['price'] < _min:
                _min_index = i

        found_ticket = {
            'fly_duration': datas[_min_index]['fly_duration'],
            'cityFrom': datas[_min_index]['cityFrom'],
            'cityTo': datas[_min_index]['cityTo'],
            'price': datas[_min_index]['price'],
            'booking_token': datas[_min_index]['booking_token'],
            'dTimeUTC': datas[_min_index]['dTimeUTC'],
            'time': datetime.datetime.fromtimestamp(datas[_min_index]['dTimeUTC']).replace(tzinfo=datetime.timezone.utc)
        }

        # get answer from check_booking()
        answer = check_booking(found_ticket['booking_token'], adults_count, children_count, infants_count)

    context = {
        # 'dates': dates
        'directions': DIRECTIONS,
        'directions_table': directions_table,
        'found_ticket': found_ticket,
        'answer': answer
    }

    return render(request, 'fly_app/index.html', context)


def cheap_tickets_calendar(request):
    """ Веб-сервис, который выводит самый дешевый билет за текущий месяц по заданному направлению """

    # dictionary that will have all necessary data to show to the users
    ticket_data = []
    min_ticket_data = {}
    fly_from, fly_to = (None, None)

    if request.GET.get("fly_from") and request.GET.get("fly_to"):

        # init current day and second date with a difference of 30 days
        date_from = datetime.date.today().strftime('%d/%m/%Y')
        date_to = (datetime.date.today() + datetime.timedelta(days=5)).strftime('%d/%m/%Y')

        # get user inputs
        fly_from = request.GET.get("fly_from")
        fly_to = request.GET.get("fly_to")
        print(f"fly_from: {fly_from} // fly_to: {fly_to}")

        # make GET request to the service to get prices data
        r = requests.get(f'{settings.BASE_URL}/flights?fly_from={fly_from}&fly_to={fly_to}&date_from={date_from}'
                         f'&date_to={date_to}&adults=1&partner={settings.PARTNER}&curr=KZT', headers=HEADERS)

        if r.status_code == 200:
            # get data from response
            dir_data = r.json()['data']
            print("--------- dir_data ------------")

            # init min_price_index to the first element's index
            min_price_index = 0
            for i in range(len(dir_data)):
                ticket_data.append({
                    "price": dir_data[i]["price"],
                    "booking_token": dir_data[i]["booking_token"],
                    "airline": dir_data[i]["airlines"][0],
                    "dep_time": datetime.datetime.fromtimestamp(dir_data[i]["dTime"]).strftime('%d-%m-%Y %H:%M:%S'),
                    "duration": dir_data[i]["fly_duration"],
                    "arr_time": datetime.datetime.fromtimestamp(dir_data[i]["aTime"]).strftime('%d-%m-%Y %H:%M:%S'),
                })
                if dir_data[i]['price'] < dir_data[min_price_index]['price']:
                    min_price_index = i

            # pprint.pprint(dir_data[min_price_index])
            # init ticket_data with price and booking_token and other necessary data
            min_ticket_data["price"] = dir_data[min_price_index]["price"]
            min_ticket_data["booking_token"] = dir_data[min_price_index]["booking_token"]
            min_ticket_data["airline"] = dir_data[min_price_index]["airlines"][0]
            min_ticket_data["dep_time"] = datetime.datetime.fromtimestamp(dir_data[min_price_index]["dTime"])\
                .strftime('%d-%m-%Y %H:%M:%S')
            min_ticket_data["duration"] = dir_data[min_price_index]["fly_duration"]
            min_ticket_data["arr_time"] = datetime.datetime.fromtimestamp(dir_data[min_price_index]["aTime"]) \
                .strftime('%d-%m-%Y %H:%M:%S')
            # print(f"price: {ticket_data['price']} // booking_token: {ticket_data['booking_token']} // "
            #       f"airline: {ticket_data['airline']}")

    context = {
        'directions': DIRECTIONS,
        'fly_from': fly_from,
        'fly_to': fly_to,
        'ticket_data': ticket_data,
        'min_ticket_data': min_ticket_data
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
                    bd["dep_time"] = datetime.datetime.fromtimestamp(rd["flights"][0]["dtime"])\
                        .strftime('%d-%m-%Y %H:%M:%S')
                    bd["arr_time"] = datetime.datetime.fromtimestamp(rd["flights"][0]["atime"]) \
                        .strftime('%d-%m-%Y %H:%M:%S')
                    bd["duration"] = datetime.datetime.fromtimestamp(rd["flights"][0]["atime"]) - datetime.datetime.\
                        fromtimestamp(rd["flights"][0]["dtime"])
                    bd["total"] = rd["total"]
                    bd["price_change"] = rd["price_change"]
                break
            time.sleep(30)

        context = {
            "bd": bd
        }
        return render(request, 'fly_app/booking.html', context)
