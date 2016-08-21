/usr/sbin/i2cset -f -y 0 0x34 0x93 0x0
echo 4096 | /usr/bin/tee /proc/asound/card0/pcm0p/sub0/prealloc
/usr/bin/python escape.py
