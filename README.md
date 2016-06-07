# PyModMon
Python Modbus Monitor

This is a Python skript that acts as a Modbus slave.
It can be used e.g. for reading data from newer solar inverters made by SMA.

It has the ability to monitor several modbus addresses with a configurable interval and can also write the received data to a csv file.

The logged data can then be used with other programs for analysing or plotting.

Dependencies:
* Python 2.7
* Python package docopt
* Python package pymodbus (and dependencies)
