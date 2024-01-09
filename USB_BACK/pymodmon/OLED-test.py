# coding=utf-8
# Python Version 2.7
# display.py
#------------------------------------------------------------
 
# Einbindung der notwendigen Grundbibliotheken
import os, sys, time, threading
 
# Einbindung 0,96 Zoll OLED Display 128x64 Pixel
import Adafruit_SSD1306
from PIL import Image, ImageDraw, ImageFont
 
# Global für Aktivitätsstatus einzelner Threads/Programmteile
Display_aktiv = True
Thread_Sensoren_aktiv = True
 
 
# Funktionen
#-----------------------------
 
def aktuelleZeit(werta, wertb):
 zeitpunktMessung = time.localtime()
 jahr, monat, tag = zeitpunktMessung[0:3]
 stunde, minute, sekunde = zeitpunktMessung[3:6]
 systemUhrzeit = str(stunde).zfill(2) + ":" + str(minute).zfill(2) + ":" + str(sekunde).zfill(2)
 systemDatum = str(tag).zfill(2) + "." + str(monat).zfill(2) + "." + str(jahr)
 if werta == "time" and wertb == "date":
    ermittelteZeit = systemUhrzeit + " " + systemDatum
 elif werta == "date" and wertb == "time":
    ermittelteZeit = systemDatum + " " + systemUhrzeit
 elif werta == "time" and wertb == "":
    ermittelteZeit = systemUhrzeit
 elif werta == "date" and wertb == "":
    ermittelteZeit = systemDatum
 else:
    ermittelteZeit = zeitpunktMessung
 return ermittelteZeit
 
 
# Display einrichten
 
# Raspberry Pi pin configuration:
RST = 24
 
# Display 128x64 display with hardware I2C:
disp = Adafruit_SSD1306.SSD1306_128_64(rst=RST)
 
# Initialize library.
disp.begin()
 
# Clear display.
disp.clear()
disp.display()
 
# Create blank image for drawing.
# Make sure to create image with mode '1' for 1-bit color.
width = disp.width
height = disp.height
image = Image.new('1', (width, height))
 
# Get drawing object to draw on image.
draw = ImageDraw.Draw(image)
 
# Draw a black filled box to clear the image.
draw.rectangle((0,0,width,height), outline=0, fill=0)
 
# First define some constants to allow easy resizing of shapes.
padding = 2
shape_width = 20
top = padding
bottom = height-padding
 
# Move left to right keeping track of the current x position for drawing shapes.
x = padding
 
# Load default font.
font = ImageFont.load_default() # Wenn keine eigene Schrift vorhanden ist!!!! 
# font = ImageFont.truetype("font/arial.ttf", 12) # Schriftart, Schriftgröße
# font_b = ImageFont.truetype("font/arial.ttf", 18)
# font_c = ImageFont.truetype("font/arial.ttf", 14)
 
# Write one line of text.
draw.text((x, top+25), 'Start', font=font, fill=255)
 
# Display image.
disp.image(image)
disp.display()
 
 
# Hauptroutine
 
while Display_aktiv:
 draw.rectangle((0,0,width,height), outline=0, fill=0) #Display leeren
 displayTime = aktuelleZeit("time", "date") # bei Abfrage "date","time" ändert die Reihenfolge der Ausgabe
 draw.line((x, top+45, x+width, top+45), fill=255)
 draw.text((x, top+50), displayTime, font=font, fill=255)
 disp.image(image)
 disp.display()
