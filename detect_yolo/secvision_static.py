import datetime
import logging
import os
from secvision_web import aiohttp_server, run_server
import threading

channel_names = {
    '101': 'Front lawn',
    '201': 'Front door',
    '301': 'Driveway',
    '401': 'Side gate',
    '501': 'Courtyard',
    '601': 'Garage gate',
    '701': 'Back Lawn',
    '801': 'Pool'
}


def initworkers(obj) -> None:
    e = threading.Event()
    channel_event_worker = threading.Thread(name='channel-event-daemon', target=channel_event_work,
                                            args=(e, obj, 5))
    channel_event_worker.setDaemon(True)
    channel_event_worker.start()

    webserver = threading.Thread(target=run_server, args=(aiohttp_server(obj),))
    webserver.start()


def channel_event_work(event: threading.Event, obj, time: float) -> None:
    while not event.isSet():
        zone_done_event_handler = []
        channel_done_event_handler = []

        event_is_set = event.wait(time)
        if event_is_set:
            logging.debug('processing event')
        else:
            # Give us stats every minute or so . . .
            obj.cnt += 1
            if obj.cnt == 12:
                obj.cnt = 0
                ao_temp, cpu_temp, gpu_temp, pll_temp, rpm, thermal = jetson_metrics()
                net_speed = sum(obj.network_speed) / len(obj.network_speed)
                log_metrics(ao_temp, cpu_temp, gpu_temp, pll_temp, rpm, thermal, net_speed)

            # Do some work if there is a channel event
            if len(obj.sv_channel_event) > 0:
                for channel in obj.sv_channel_event:
                    # Checks channel event timestamp
                    if float(obj.sv_channel_event[channel]) > 0:
                        elapsed = datetime.datetime.now() - datetime.datetime.fromtimestamp(
                            obj.sv_channel_event[channel])
                        logging.warning(
                            f" {channel_names[channel]} person found {elapsed.total_seconds()}s ago")

                        # Checks if the channel event is older than 15s and then stops the zone recording.
                        # TODO: Zoneless operation
                        #  These zones would be redundant if recordings where triggered on a per channel basis
                        #  non electrically...
                        if elapsed > datetime.timedelta(seconds=15):
                            zone = obj.determine_zone(channel)
                            if zone == 1:
                                if len(obj.zone1) == 1:
                                    zone_done_event_handler.append(channel)
                                else:
                                    channel_done_event_handler.append(channel)
                                obj.zone1.pop(channel, None)
                            elif zone == 2:
                                if len(obj.zone2) == 1:
                                    zone_done_event_handler.append(channel)
                                else:
                                    channel_done_event_handler.append(channel)
                                obj.zone2.pop(channel, None)
                            elif zone == 3:
                                if len(obj.zone3) == 1:
                                    zone_done_event_handler.append(channel)
                                else:
                                    channel_done_event_handler.append(channel)
                                obj.zone3.pop(channel, None)
                            else:
                                if len(obj.zone4) == 1:
                                    zone_done_event_handler.append(channel)
                                else:
                                    channel_done_event_handler.append(channel)
                                obj.zone4.pop(channel, None)

                # Does work on the channel done event
                for channel in channel_done_event_handler:
                    obj.sv_channel_event.pop(channel, None)

                # Does work on the zone done event
                for channel in zone_done_event_handler:
                    obj.sv_channel_event.pop(channel, None)
                    obj.sv_garbage_collector.append(channel)


def log_metrics(ao_temp, cpu_temp, gpu_temp, pll_temp, rpm, thermal, net):
    logging.info(
        f" CPU {int(cpu_temp) / 1000:.2f}°C / GPU {int(gpu_temp) / 1000:.2f}°C /"
        f" PLL {int(pll_temp) / 1000:.2f}°C")
    logging.info(
        f" AO {int(ao_temp) / 1000:.2f}°C / THERM {int(thermal) / 1000:.2f}°C / FAN {round(rpm, 0)}RPM ")
    logging.info(
        f" NETWORK {net:.2f} FPS ")


def jetson_metrics():
    fan_rpm = 2000
    # Jetson thermal sensors
    ao_temp = os.popen("cat /sys/devices/virtual/thermal/thermal_zone0/temp").read()
    cpu_temp = os.popen("cat /sys/devices/virtual/thermal/thermal_zone1/temp").read()
    gpu_temp = os.popen("cat /sys/devices/virtual/thermal/thermal_zone2/temp").read()
    pll_temp = os.popen("cat /sys/devices/virtual/thermal/thermal_zone3/temp").read()
    pmic_temp = os.popen("cat /sys/devices/virtual/thermal/thermal_zone4/temp").read()
    thermal = os.popen("cat /sys/devices/virtual/thermal/thermal_zone5/temp").read()
    # input_voltage = os.popen("cat /sys/bus/i2c/drivers/ina3221x/6-0040/iio\:device0/in_voltage0_input").read()
    # Fan PWM reading
    pwm = os.popen("cat /sys/devices/pwm-fan/hwmon/hwmon1/cur_pwm").read()
    rpm = int(pwm) * (fan_rpm / 256)
    return ao_temp, cpu_temp, gpu_temp, pll_temp, rpm, thermal
