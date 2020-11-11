from django.conf import settings

from celery import shared_task
from redis import Redis
import pickle
import datetime
import requests
import sys


redis_cli = Redis(host=settings.REDIS_HOST, port=settings.REDIS_PORT)


DIRECTIONS = ['ALA-TSE', 'TSE-ALA', 'ALA-MOW', 'MOW-ALA', 'ALA-CIT', 'CIT-ALA', 'TSE-MOW', 'MOW-TSE',
              'TSE-LED', 'LED-TSE']
HEADERS = {
    'Content-Type': 'application/json'
}


@shared_task
def init_cache():
    """ Задача для Celery, которая обновляет/заполняет кэш направлений и цен """

    # init current day and second date with a difference of 30 days
    date_from = datetime.date.today().strftime('%d/%m/%Y')
    date_to = (datetime.date.today() + datetime.timedelta(days=30)).strftime('%d/%m/%Y')

    for direction in DIRECTIONS:
        print("----------------------------------------------------")
        print(f"direction: {direction}")
        new_ticket_data = []
        fly_from = direction.split('-')[0]
        fly_to = direction.split('-')[1]
        print(f"fly_from: {fly_from} // fly_to: {fly_to}")

        # make GET request to the service to get prices data
        r = requests.get(f'{settings.BASE_URL}/flights?fly_from={fly_from}&fly_to={fly_to}&date_from={date_from}'
                         f'&date_to={date_to}&adults=1&partner={settings.PARTNER}&curr=KZT', headers=HEADERS)
        if r.status_code == 200:
            dir_data = r.json()['data']
            cd = datetime.date.today()
            min_i = 0
            for i in range(31):
                mi = None
                for j in range(len(dir_data)):
                    if datetime.datetime.fromtimestamp(dir_data[j]["dTime"]).date() == cd:
                        if mi is None:
                            mi = j
                        if dir_data[j]['price'] < dir_data[mi]['price']:
                            mi = j
                        if dir_data[mi]['price'] < dir_data[min_i]['price']:
                            min_i = j

                if mi is not None:
                    new_ticket_data.append({
                        "price": dir_data[mi]["price"],
                        "booking_token": dir_data[mi]["booking_token"],
                        "airline": dir_data[mi]["airlines"][0],
                        "dep_time": datetime.datetime.fromtimestamp(dir_data[mi]["dTime"]).strftime(
                            '%d-%m-%Y %H:%M:%S'),
                        "duration": dir_data[mi]["fly_duration"],
                        "arr_time": datetime.datetime.fromtimestamp(dir_data[mi]["aTime"]).strftime(
                            '%d-%m-%Y %H:%M:%S'),
                    })
                cd = cd + datetime.timedelta(days=1)

            print("-------- min price -----------")
            min_price = dir_data[min_i]['price']
            print(min_price)
            print("-------------------------------")
            red_d = {
                "min_price": min_price,
                "ticket_data": new_ticket_data
            }

            # delete old cache and write new data only if there is new data about tickets
            if new_ticket_data:
                # delete from Redis old tickets data
                try:
                    redis_cli.delete(direction)
                    print(f"Deleted cache from {direction} key")
                except:
                    err = sys.exc_info()
                    print(f"Error occurs when delete old tickets data from redis! {err[-1].tb_lineno, err}")

                # write to Redis
                try:
                    redis_cli.set(direction, pickle.dumps(red_d))
                    print(f"wrote new data to cache to key: {direction}")
                except:
                    err = sys.exc_info()
                    print(f"Error occurs when write tickets data to redis! {err[-1].tb_lineno, err}")
