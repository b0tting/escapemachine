import ConfigParser
import logging
import os
import pygame

from flask import Flask, render_template, jsonify
import time
import atexit
import sys
import re
from escape_library import OutputPin, CaravanLoggingHandler

chip_complete_mode = False
try:
    import RPi.GPIO as GPIO
    GPIO.setmode(GPIO.BCM)
    chip_complete_mode = True
except Exception:
    GPIO = False


## Prereqs: python 2.7 (PYTHON 3 MAG NAAR DE HEL)
## apt-get install git build-essential python-dev python-pip flex bison python-pygame -y
## pip install flask
##


## Logger setup
logger = logging.getLogger(__name__)
logging.getLogger('werkzeug').setLevel(logging.ERROR)
entriesHandler = CaravanLoggingHandler()
logger.addHandler(logging.StreamHandler())
logger.addHandler(entriesHandler)
logger.setLevel(logging.INFO)


## Constants
STATE_NORMAL = 10
STATE_KEYTIME = 11
STATE_AFTER_KEYTIME = 12
STATE_START = 13
readeable_states = {STATE_START:'Standby',STATE_NORMAL:'Entree',STATE_KEYTIME:'Badkamer',STATE_AFTER_KEYTIME:'Eindspel'}

app = Flask(__name__)

def clean():
    logger.info("Exit coming up, cleaning GPIO and mixer")
    pygame.mixer.quit()
    if GPIO:
        GPIO.cleanup()

## Given time, the state machine should be migrated to it's own class and use
## external XML or sorts to define states. Seeing the clear purpose of the current
## version I'm not investing time in that yet.
def run_state_machine(self):
    ## Measuring buttons states before investigating current state
    time.sleep(0.3)
    bookspushed = GPIO.input(bookbuttonspin)
    keypushed = GPIO.input(keybuttonpin)
    logger.info("Buttons push, now in: books " + str(bookspushed) + ", key " + str(keypushed))

    ## Nobody said it had to be hard!
    if not bookspushed and state == STATE_NORMAL:
        logger.info("Correct buttons pushed for bathroom state")
        state_machine_bathroom()
    elif not keypushed and state == STATE_KEYTIME:
        logger.info("Correct buttons pushed for endgame state")
        state_machine_endgame()

def state_machine_start():
    global state
    state = STATE_START ## standby
    logger.info("Now going into state " + readeable_states[state])
    spot.turn_off()
    lamp.turn_off()
    magnet.turn_off()
    stop_music()

def state_machine_reset():
    global state
    state = STATE_NORMAL
    logger.info("Now going into state " + readeable_states[state])
    spot.turn_off()
    lamp.turn_on()
    magnet.turn_on()
    play_music(sounddir + config.get("Escape","music_state_entree"))
    play_scene_sound("sound_effect_entree")

def state_machine_bathroom():
    global state
    state = STATE_KEYTIME
    logger.info("Now going into state " + readeable_states[state])
    lamp.turn_off()
    magnet.turn_off()
    spot.turn_on()
    play_music(sounddir + config.get("Escape","music_state_bathroom"))
    play_scene_sound("sound_effect_bathroom")

def state_machine_endgame():
    global state
    state = STATE_AFTER_KEYTIME
    logger.info("Now going into state " + readeable_states[state])
    spot.turn_off()
    magnet.turn_off()
    lamp.turn_on()
    play_music(sounddir + config.get("Escape","music_state_endgame"))
    play_scene_sound("sound_effect_endgame")

def button_listener_thread(pin):
    logger.info(str(pin) + " listener up for reading")
    while True:
        logger.info(str(pin))
        GPIO.wait_for_edge(pin, GPIO.BOTH)
        logger.info(str(pin) + " got edge!")
        run_state_machine()
        time.sleep(1)

def setup_pin(pin, input=True):
    if input and GPIO:
        GPIO.setup(pin, GPIO.IN)
        
        ## button_thread = Thread(target = button_listener_thread, args = (pin,))
        ## button_thread.daemon = True
        ## button_thread.start()
    return pin

   

def play_scene_sound(scene_sound):
    if config.has_option('Escape', scene_sound):
        play_sound(sounddir + config.get("Escape", scene_sound))

## Sound code, used for calling hints to the players
sound_channel = None
last_soundpath = ""
def play_sound(soundpath):
    logger.info("Got request to play "+ soundpath)
    global sound_channel, last_soundpath
    try:
        ## Kill ALL current sounds except for music
        pygame.mixer.stop()

        if not os.path.exists(soundpath):
            logger.error(soundpath + " does not exist")

        if soundpath[-3:] != "ogg":
            logger.error("File requested was of type: " + soundpath[-3:] + " and might not work!")


        ## Calculate length first. This takes a few seconds on the c.h.i.p.
        hint = pygame.mixer.Sound(soundpath)
        hint.set_volume(float(sound_volume) / 100)
        length = hint.get_length()
        logger.info("Length of sound bit is "+ str(int(length)) + " seconds.")

        ## Before playing, lower the volume of the music
        if pygame.mixer.music.get_busy():
            if(pygame.mixer.music.get_volume() > 0.2):
                pygame.mixer.music.set_volume(0.2)
            else:
                pygame.mixer.music.set_volume(0.0)
        last_soundpath = soundpath
        sound_channel = hint.play()
        if pygame.mixer.music.get_busy():
            time.sleep(length +1)
            pygame.mixer.music.set_volume(float(music_volume) / 100)

    except Exception, e:
        logger.error("Tried to play sound file but got error: " + str(e))
    logger.info("Done with " + soundpath)


## Background music, changes for each scene
## Note that the fade blocks the state_machine from ansering requests, so in theory if players are fast they
## will need to pull triggers multiple times
music = None
def play_music(soundpath):
    stop_music()
    global music
    pygame.mixer.music.load(soundpath)
    music = soundpath
    pygame.mixer.music.set_volume(float(music_volume) / 100)
    pygame.mixer.music.play(-1)

def stop_music():
    fade = config.getint("Escape","fadeout")
    if pygame.mixer.music.get_busy():
        pygame.mixer.music.fadeout(fade * 1000)
        time.sleep(fade)
    global music
    music = None

def get_sounds_from_folder(dir):
    return sorted([f for f in os.listdir(dir) if re.search(r'.+\.(wav|ogg|mp3)$', f)])


### FLASK METHODS

@app.route('/state')
def flask_state():
    playing_sound = last_soundpath if (sound_channel and sound_channel.get_busy()) else False
    playing_music = music if pygame.mixer.music.get_busy() else False
    outputpinstates = {pinname: pin.is_on for (pinname, pin) in outputpins.iteritems()}
    return jsonify(state=readeable_states[state],
                   sound=playing_sound,
                   music=playing_music,
                   outputpins=outputpinstates,
                   logs=entriesHandler.get_last_entries()
                   )

@app.route('/play/<filename>')
def flask_play(filename):
    play_sound(sounddir + filename)
    return jsonify(result="ok")

@app.route('/setvolume/<volume_type>/<volume>')
def flask_set_volume(volume_type, volume):
    global music_volume, sound_volume
    logger.info("Setting " + volume_type + " to " + volume)
    if volume_type == "music_volume":
        music_volume = volume
        pygame.mixer.music.set_volume(float(music_volume) / 100)
    else:
        sound_volume = volume
        if sound_channel:
            sound_channel.set_volume(float(sound_volume) / 100)
    return jsonify(result="ok")

@app.route('/state/<newstate>')
def flask_set_state(newstate):
    logger.info("Got web request for state " + newstate)
    if newstate == readeable_states[STATE_START]:
        state_machine_start()
    elif newstate == readeable_states[STATE_NORMAL]:
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
    to_on = newstate == "1"
    logger.info("Got web request to turn pin " + pin.name + (" ON" if to_on else " OFF"))
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
    return render_template("index.html",
                           sounds=get_sounds_from_folder(sounddir),
                           states=readeable_states,
                           outputpins = outputpins,
                           max_time=config.get("Escape", "max_time"),
                           refresh_state=config.getint("Escape", "refresh_browser_time"),
                           sound_volume = sound_volume,
                           music_volume = music_volume)


## Init stuff from here
configfilename = "escape.conf"
configfile = (os.path.join(os.getcwd(), configfilename))
config = ConfigParser.SafeConfigParser()
try:
    with open(configfile,'r') as configfilefp:
        config.readfp(configfilefp)
except:
    print("Could not read " + configfile)
    sys.exit()

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
bookbuttonspin = config.getint("Escape", "bookbuttonspin")
GPIO.setup(bookbuttonspin, GPIO.IN)
GPIO.add_event_detect(bookbuttonspin, GPIO.BOTH, callback=run_state_machine, bouncetime=200)

keybuttonpin = config.getint("Escape", "keybuttonpin")
GPIO.setup(keybuttonpin, GPIO.IN)
GPIO.add_event_detect(keybuttonpin, GPIO.BOTH, callback=run_state_machine, bouncetime=200)

lamp = OutputPin(config.getint("Escape", "lamppin"), "Lamp")
time.sleep(0.5)
spot = OutputPin(config.getint("Escape", "spotpin"), "Spot")
time.sleep(0.5)
magnet = OutputPin(config.getint("Escape", "magnetpin"), "Magnet")
outputpins = {lamp.name:lamp, spot.name:spot,magnet.name:magnet}
sounddir = config.get("Escape", "sounddir") + "/"
music_volume = config.getfloat("Escape", "music_volume")
sound_volume = config.getfloat("Escape", "sound_volume")
pygame.mixer.music.set_volume(music_volume / 100)

## Default setting is state_normal. By running reset we set all the switches in the correct
## order.
state_machine_start()
state = STATE_START

if chip_complete_mode:
    logger.error("CHIP_IO found, running on CHIP mode")
else:
    logger.error("CHIP_IO NOT found. Running in fake mode")

debug = config.getboolean("Escape", "debug")
if debug:
    logger.error("Running in debug mode, app will restart.")
    if chip_complete_mode:
        logger.error("This might cause weird behaviour on the CHIP, so please don't do that")

logger.error("Starting app complete")


app.run(debug=config.getboolean("Escape", "debug"),host="0.0.0.0",port=config.getint("Escape", "port"),threaded=True)
