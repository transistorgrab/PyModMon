#!/bin/sh

ps auxw | grep pymodmon | grep -v grep > /dev/null

if [$0 != 0]
then
    python /media/USB256/pymodmon/pymodmon.py -i /media/USB256/pymodmon/SunnyBoy25_cli.ini -D
fi
