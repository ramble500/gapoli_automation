import datetime
import logging
import os

from influxdb import InfluxDBClient

logger = logging.getLogger(__name__)

influx = None


def init_influx(suffix=None):
    global influx

    INFLUX_HOST = os.environ.get("INFLUX_HOST")
    if INFLUX_HOST is None:
        return

    INFLUX_PORT = int(os.environ.get("INFLUX_PORT", 8086))

    dbname = "gabbot"
    if suffix is not None:
        dbname = f"gabbot_{suffix}"

    influx = InfluxDBClient(INFLUX_HOST, INFLUX_PORT, database=dbname)
    try:
        influx.create_database(dbname)
    except:
        pass


def write_influx(measurement, fields):
    if influx is not None:
        influx.write_points(
            [
                {
                    "measurement": measurement,
                    "time": datetime.datetime.now(datetime.timezone.utc),
                    "fields": fields,
                }
            ]
        )


def write_influx_manual(objs: list):
    influx.write_points(objs)
