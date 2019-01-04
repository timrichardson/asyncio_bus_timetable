from ptv.client import PTVClient,RouteType
from timetable_logic import ptv_api_settings
from datetime import datetime,timezone,timedelta
from typing import List
from dateutil.parser import parse
from concurrent.futures import ThreadPoolExecutor,TimeoutError
import time
import logging
log = logging.getLogger(__name__)
log.setLevel(logging.DEBUG)

executor = ThreadPoolExecutor(max_workers=1)

def utc_to_local(utc_dt):
    return utc_dt.replace(tzinfo=timezone.utc).astimezone(tz=None)

def create_ptv_api()->PTVClient:
    return PTVClient(dev_id=ptv_api_settings.ptv_userid,
                     api_key=ptv_api_settings.ptv_key)


def stops_near(client):
    json = client.get_stop_near_location(-37.8014269, 145.0664683)
    return json

def filter_departures(get_departure_json:dict,start_time:datetime=None)->List[datetime]:
    start_time = start_time or datetime.now(timezone.utc) - timedelta(minutes=5)
    next_scheduled_departures = [d['scheduled_departure_utc']
        for d in get_departure_json['departures'] if d['scheduled_departure_utc'] > start_time.isoformat()]

    #convert to a list of datetimes
    next_scheduled_departures_datetime = [utc_to_local(parse(dept_str)) for dept_str in next_scheduled_departures[:5]]
    return next_scheduled_departures_datetime



def next_buses(ptv_client,stop_name:str)->List[datetime]:

    def local_get_departure_from_stop():
        return ptv_client.get_departure_from_stop(RouteType.BUS, ptv_api_settings.stops[stop_name],
                                          include_cancelled=False,)

    log.info(f"{datetime.now()}: submitting future")
    future_req = executor.submit(local_get_departure_from_stop)
    try:
        json = future_req.result(timeout=10)
        log.info(f"{datetime.now()}: future succeeded")
        dept_list = filter_departures(get_departure_json=json)
        return dept_list
    except TimeoutError:
        json = None
        log.error(f"{datetime.now()}: timeout when fetching API data from PTV")
        return []

    # json = client.get_departure_from_stop(RouteType.BUS, ptv_api_settings.stops[stop_name],
    #                                       include_cancelled=False,)





if __name__ == '__main__':
    client = create_ptv_api()
    departures_lawson = next_buses(ptv_client=client,stop_name='Lawson')
    departures_para = next_buses(ptv_client=client,stop_name='Para')
    print (departures_lawson,departures_para)
    executor.shutdown()
