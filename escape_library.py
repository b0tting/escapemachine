from collections import OrderedDict
import logging
import imp
try:
    imp.find_module('CHIP_IO')
    import CHIP_IO.GPIO as GPIO
except ImportError:
    GPIO = False
import datetime
import time


class CaravanLoggingHandler(logging.StreamHandler):
    def __init__(self):
        logging.StreamHandler.__init__(self)
        self.last_entries = OrderedDict()

    def emit(self, record):
        msg = self.format(record)
        if len(self.last_entries) > 30:
            self.last_entries.popitem(last=False)
        self.last_entries[datetime.datetime.now()] = msg

    def get_last_entries(self):
        nowsecs = time.time()
        returns = []
        for dateentry in self.last_entries:
            thensecs = time.mktime(dateentry.timetuple())
            diff = thensecs - nowsecs
            diffstring = str(int(diff)) + " secs"
            returns.insert(0, diffstring.ljust(9) + " " + self.last_entries[dateentry])
        return returns


class OutputPin:
    def __init__(self, pin, name):
        self.name = name
        self.pin = pin
        if GPIO:
            GPIO.setup(pin, GPIO.OUT)
            GPIO.output(pin, GPIO.LOW)
        self.is_on = False

    def flip_switch(self, to_high):
        if GPIO:
            state = GPIO.HIGH if to_high else GPIO.LOW
            GPIO.output(self.pin, state)
        self.is_on = not to_high

    def turn_on(self):
        self.flip_switch(False)

    def turn_off(self):
        self.flip_switch(True)

