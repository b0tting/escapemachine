# escapemachine
A python script for supporting Escape Room puzzles with a c.h.i.p. (getchip.com)

# Features
The CHIP runs the following functions:
- Allow the game master to play spoken hints and sound effects, from a previously placed set of sound files
- Play the background music for the escape room, with fading over to other tracks on scene changes
- Follow scene progression from a phone, allow for direct intervention by enabling or disabling individual relays
- Show a countdown timer and log scene changes

# Interface 
The interface was built using materializecss and is aimed at phone and tablet use. 

# Technically..
..you could easily convert this script for use on a raspberry pi or any other SBC with IO pins. However, the CHIP is such a cool thing, I'd go for that if you can find one. The scene setup is extremely simple python code and easy to convert for other rooms, the UI is dynamic and should follow the python config. Also, someday, one day, I will enable configuration using XML or JSON. 
