import ConfigParser
import logging
import os
import pygame
from threading import Thread
import CHIP_IO.GPIO as GPIO
from flask import Flask, render_template, jsonify
import time
import atexit
import sys
import re
from escape_library import OutputPin, CaravanLoggingHandler

## todo: Access point configuratie

## Prereqs: python 2.7 (PYTHON 3 MAG NAAR DE HEL)
## apt-get install git build-essential python-dev python-pip flex bison python-pygame -y
## pip install flask
##

logger = logging.getLogger(__name__)
logging.getLogger('werkzeug').setLevel(logging.ERROR)
entriesHandler = CaravanLoggingHandler()
logger.addHandler(logging.StreamHandler())
logger.addHandler(entriesHandler)
logger.setLevel(logging.INFO)

STATE_NORMAL = 10
STATE_KEYTIME = 11
STATE_AFTER_KEYTIME = 12
readeable_states = {STATE_NORMAL:'Entree',STATE_KEYTIME:'Badkamer',STATE_AFTER_KEYTIME:'Eindspel'}

app = Flask(__name__)
configfilename = "escape.conf"
configfile = (os.path.join(os.getcwd(), configfilename))
config = ConfigParser.SafeConfigParser()
try:
    with open(configfile,'r') as configfilefp:
        config.readfp(configfilefp)
except:
    print("Could not read " + configfile)
    sys.exit()

def clean():
    logger.info("Exit coming up, cleaning GPIO and mixer")
    pygame.mixer.quit()
    GPIO.cleanup()


def run_state_machine():
    ## Measuring buttons states before investigating current state
    book1pushed = not GPIO.input(bookbutton1pin)
    book2pushed = not GPIO.input(bookbutton2pin)
    keypushed = not GPIO.input(keybuttonpin)
    logger.info("Buttons push, now in: pin1 " + str(book1pushed) + ", pin2 " + str(book2pushed) + ", pin3 " + str(keypushed))

    ## Nobody said it had to be hard!
    if not book1pushed and not book2pushed and state == STATE_NORMAL:
        logger.info("Correct buttons pushed for bathroom state")
        state_machine_bathroom()
    elif not keypushed and state == STATE_KEYTIME:
        logger.info("Correct buttons pushed for endgame state")
        state_machine_endgame()

def state_machine_reset():
    global state
    state = STATE_NORMAL
    logger.info("Now going into state " + readeable_states[state])
    spot.turn_off()
    lamp.turn_on()
    magnet.turn_on()

def state_machine_bathroom():
    global state
    state = STATE_KEYTIME
    logger.info("Now going into state " + readeable_states[state])
    lamp.turn_off()
    magnet.turn_off()
    spot.turn_on()
    play_sound(sounddir + bathroomeffect)

def state_machine_endgame():
    global state
    state = STATE_AFTER_KEYTIME
    logger.info("Now going into state " + readeable_states[state])
    spot.turn_off()
    magnet.turn_off()
    lamp.turn_on()

def button_listener_thread(pin):
    logger.info(pin + " listener up for reading")
    while True:
        GPIO.wait_for_edge(pin, GPIO.BOTH)
        logger.info(pin + " got edge!")
        run_state_machine()
        time.sleep(1)

def setup_pin(pin, input=True):
    if input:
        GPIO.setup(pin, GPIO.IN)
        ButtonThread = Thread(target = button_listener_thread, args = (pin,))
        ButtonThread.daemon = True
        ButtonThread.start()
    return pin

current_sound = ""
def play_sound(soundpath):
    logger.info("Got request to play "+ soundpath)
    global current_sound
    current_sound = soundpath
    try:
        pygame.mixer.music.load(soundpath)
        pygame.mixer.music.play()
    except Exception, e:
        logger.error("Tried to play sound file but got error: " + str(e))


def get_sounds_from_folder(dir):
    return [f for f in os.listdir(dir) if re.search(r'.+\.(wav|ogg|mp3)$', f)]

@app.route('/state')
def flask_state():
    playing = current_sound if pygame.mixer.music.get_busy() else False
    outputpinstates = {pinname: pin.is_on for (pinname, pin) in outputpins.iteritems()}
    return jsonify(state=readeable_states[state],sound=playing,outputpins=outputpinstates,logs=entriesHandler.get_last_entries())

@app.route('/play/<filename>')
def flask_play(filename):
    play_sound(sounddir + filename)
    return jsonify(result="ok")

@app.route('/state/<newstate>')
def flask_set_state(newstate):
    logger.info("Got web request for state " + newstate)
    if newstate == readeable_states[STATE_NORMAL]:
        state_machine_reset()
    elif newstate == readeable_states[STATE_KEYTIME]:
        state_machine_bathroom()
    else:
        state_machine_endgame()
    return jsonify(result="ok")

@app.route('/shutdown')
def flask_shutdown():
    os.system("/sbin/shutdown -h now")
    time.sleep(1)
    sys.exit()

@app.route('/reboot')
def flask_reboot():
    logger.info("Got web request for reboot")
    os.system("/sbin/reboot")
    time.sleep(1)
    sys.exit()

@app.route('/switch/<pinname>/<newstate>')
def flask_set_switch(pinname, newstate):
    pin = outputpins[pinname]
    to_on = newstate.lower() == "true"
    logger.info("Got web request to turn pin " + pin + ("ON" if to_on else "OFF"))
    try:
        if to_on:
            pin.turn_on()
        else:
            pin.turn_off()
    except Exception, e:
        logger.error("Got exception trying to turn pin, " + str(e))
    return jsonify(result="ok")

@app.route('/lastlog')
def flask_get_lastlog():
    return jsonify(lastlog=entriesHandler.get_last_entries())

@app.route('/')
def hello_world():
    return render_template("index.html", sounds=get_sounds_from_folder(sounddir), states=readeable_states,outputpins = outputpins)

## Set up mixer now while time is still cheap
if not pygame.mixer.get_init():
    logger.info("Now initalizing mixer")
    pygame.mixer.init()

## When CTRL-Cing python script, make sure that the mixer and pins are released
atexit.register(clean)

## Change logger setting here, to ERROR for less or INFO for more logging
logger.info("Now initalizing logger")
logger.setLevel(logging.INFO)

## Init all pins
logger.info("Initalizing pins")
bookbutton1pin = setup_pin(config.get("Escape", "bookbutton1pin"))
bookbutton2pin = setup_pin(config.get("Escape", "bookbutton2pin"))
keybuttonpin = setup_pin(config.get("Escape", "keybuttonpin"))
lamp = OutputPin(config.get("Escape", "lamppin"), "Lamp")
time.sleep(0.5)
spot = OutputPin(config.get("Escape", "spotpin"), "Spot")
time.sleep(0.5)
magnet = OutputPin(config.get("Escape", "magnetpin"), "Magnet")
outputpins = {lamp.name:lamp, spot.name:spot,magnet.name:magnet}

## The bathroomeffect is played in the bathroom machine scene
sounddir = config.get("Escape", "sounddir") + "/"
bathroomeffect = config.get("Escape", "bathroomeffect")
if not os.path.exists(sounddir + bathroomeffect):
    print("Could not find sound effect " + sounddir + bathroomeffect)
    sys.exit()

## Default setting is state_normal. By running reset we set all the switches in the correct
## order.
state_machine_reset()
state = STATE_NORMAL

logger.error("Starting app complete")
app.run(debug=False,host="0.0.0.0",port=80,threaded=True)




