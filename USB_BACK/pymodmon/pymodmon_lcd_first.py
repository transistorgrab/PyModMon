# coding=UTF-8

## @package pymodmon_LCD
# Python Modbus Monitor for LCD output
# a small program that uses the pymodbus package to retrieve and
# display modbus slave data.
# requires: Python 2.7, pymodbus, docopt
#
# Date created: 2017-06-11
# Author: André Schieleit

## help message to display by docopt (and parsed by docopt for command line arguments)
'''Python Modbus Monitor LCD display module.
This module will display Data on a LCD with 4 lines and 20 characters
Up to 8 data can be displayed.
When calling with commandline parameters it is possible to set the line and
column where the data will be displayed. This enables to run it multiple times
with different parameters and display them all on the same display on different
locations.

Usage:
    pymodmon_lcd.py
    pymodmon_lcd.py [-h|--help]
    pymodmon_lcd.py [--version]
    pymodmon_lcd.py -i <file>|--inifile=<file> [-L <sec>|--loginterval=<sec>] [-S|--single] [--nogui] [-P|--printtoconsole]
    pymodmon_lcd.py --ip=<IP-address> --port=<port> --id=<id> --addr=<adr> --type=<TYPE> --format=<FORM> [-L <sec>|--loginterval=<sec>] [--descr=<"descr">] [--lcdl=<lcd-line>] [--lcdc=<lcd-column>] [--unit=<"unit">] [-S|--single] 
Options:
    no options given in a xterm will open the TK interface
    -h, --help            Show this screen
    --version             Show version
    -i, --inifile=<file>  Uses the given file as input for communication and
                          log file settings and channel configuration
   --ip=<IP-address>     Use this as the IP address of the communication target
    --port=<port>         Port of the communication target
    --id=<id>             Modbus ID of the communication target
    --addr=<adr>          Address of the modbus register to read
    --type=<TYPE>         Data type of the retrieved data at a given address.
                          Allowed types: U64, U32, U16, S32, S16, STR32
    --format=<FORM>       Format of the retrieved data.
                          Allowed formats: RAW, UTF8, FIX0, FIX1, FIX2, FIX3
    --descr=<descr>       Description for the retrieved data.
                          e.g. --descr="device name"
    --unit=<unit>         Unit of the retrieved data. e.g. --unit="V"
    --lcdl=<lcd-line>     line of the lcd where the data will be output,
                          when lcdl or lcdc is omitted, the LCD will be cleared
                          and line 1 and column1 will be used
    --lcdc=<lcd-column>   column of the lcd where the data will be output
                          when lcdl or lcdc is omitted, the LCD will be cleared
                          and line 1 and column1 will be used
    -S, --single          Do only one read cycle instead of continuous reading.
    -L, --loginterval=<sec>  Read data every xx seconds. [defaul value: 5]
    -P, --printtoconsole  displays the data on console additionally to the
                          LCD on Raspberry Pi
'''

## use docopt for command line parsing and displaying help message
try:
    import docopt
except ImportError:
    try: ## for command line showerror does not work
        showerror('Import Error','docopt package was not found on your system.\nPlease install it using the command:\
                                \n"pip install docopt"')
    except:
        print ('Import errror. docopt package was not found on your system. Please install it using the command: "pip install docopt"')
from docopt import docopt
if __name__ == '__main__':
    arguments = docopt(__doc__, version='PyModMon 1.0')

## use pymodbus for the Modbus communication
try:
    from pymodbus import *
except ImportError:
    try: ## for command line showerror does not work
        showerror('Import Error','pymodbus package was not found on your system.\nPlease install it using the command:\
                                \n"pip install pymodbus"')
    except:
        print ('Import errror. pymodbus package was not found on your system. Please install it using the command: "pip install pymodbus"')

## enable execution of functions on program exit    
import atexit

## enable timed execution of the data polling
from threading import Timer

## enable file access
import os

## class for all data related things
#
class Data(object):
    ## set default values and allowed input values
    def __init__(self):
        self.inifilename = None
        self.logfilename = None
        self.logmaxbuffer = 50          ## how many records will be buffered before writing to file
        self.ipaddress = '10.0.0.42'    ## address of the communication target
        self.portno =   502             ## port number of the target
        self.modbusid = 3               ## bus ID of the target
        self.manufacturer = 'Default Manufacturer' ## arbitrary string for user conveniance
        self.loginterval = 5            ## how often should data be pulled from target in seconds
        self.moddatatype = {            ## allowed data types, sent from target
                'S32':2,
                'U32':2,
                'U64':4,
                'STR32':16,
                'S16':1,
                'U16':1
                }

        self.dataformat = ['ENUM','UTF8','FIX3','FIX2','FIX1','FIX0','RAW'] ## data format from target

        ## table of data to be pulled from target
        self.datasets = [['address','type','format','description','unit','value']]

        self.datavector = []        ## holds the polled data from target
        self.databuffer = []        ## holds the datavectors before writing to disk

## class that contains all IO specifics
class Inout:
    ## some values to check against when receiving data from target
    #  these values are read when there is not acutal value from the target available.
    #  they are the equivalent to None
    MIN_SIGNED   = -2147483648
    MAX_UNSIGNED =  4294967295

    #import
    import RPi.GPIO as GPIO 
    import time
     
    # Define GPIO to LCD mapping
    LCD_RS = 7
    LCD_E  = 8
    LCD_D4 = 25
    LCD_D5 = 24
    LCD_D6 = 23
    LCD_D7 = 18
     
    # Define some device constants
    LCD_WIDTH = 20    # Maximum characters per line
    LCD_CHR = True
    LCD_CMD = False
     
    LCD_LINE_1 = 0x80 # LCD RAM address for the 1st line
    LCD_LINE_2 = 0xC0 # LCD RAM address for the 2nd line
    LCD_LINE_3 = 0x94 # LCD RAM address for the 3rd line
    LCD_LINE_4 = 0xD4 # LCD RAM address for the 4th line
     
    # Timing constants
    E_PULSE = 0.0005
    E_DELAY = 0.0005
    
    lcd_line     = 1
    lcd_column   = 1

    def lcd_init():
      # LCD interface setup
      GPIO.setmode(GPIO.BCM)       # Use BCM GPIO numbers
      GPIO.setup(LCD_E, GPIO.OUT)  # E
      GPIO.setup(LCD_RS, GPIO.OUT) # RS
      GPIO.setup(LCD_D4, GPIO.OUT) # DB4
      GPIO.setup(LCD_D5, GPIO.OUT) # DB5
      GPIO.setup(LCD_D6, GPIO.OUT) # DB6
      GPIO.setup(LCD_D7, GPIO.OUT) # DB7
     
      # Initialise display
      lcd_byte(0x33,LCD_CMD) # 110011 Initialise
      lcd_byte(0x32,LCD_CMD) # 110010 Initialise
      lcd_byte(0x06,LCD_CMD) # 000110 Cursor move direction
      lcd_byte(0x0C,LCD_CMD) # 001100 Display On,Cursor Off, Blink Off
      lcd_byte(0x28,LCD_CMD) # 101000 Data length, number of lines, font size
      lcd_byte(0x01,LCD_CMD) # 000001 Clear display
      time.sleep(E_DELAY)
     
    def lcd_byte(bits, mode):
      # Send byte to data pins
      # bits = data
      # mode = True  for character
      #        False for command
     
      GPIO.output(LCD_RS, mode) # RS
     
      # High bits
      GPIO.output(LCD_D4, False)
      GPIO.output(LCD_D5, False)
      GPIO.output(LCD_D6, False)
      GPIO.output(LCD_D7, False)
      if bits&0x10==0x10:
        GPIO.output(LCD_D4, True)
      if bits&0x20==0x20:
        GPIO.output(LCD_D5, True)
      if bits&0x40==0x40:
        GPIO.output(LCD_D6, True)
      if bits&0x80==0x80:
        GPIO.output(LCD_D7, True)
     
      # Toggle 'Enable' pin
      lcd_toggle_enable()
     
      # Low bits
      GPIO.output(LCD_D4, False)
      GPIO.output(LCD_D5, False)
      GPIO.output(LCD_D6, False)
      GPIO.output(LCD_D7, False)
      if bits&0x01==0x01:
        GPIO.output(LCD_D4, True)
      if bits&0x02==0x02:
        GPIO.output(LCD_D5, True)
      if bits&0x04==0x04:
        GPIO.output(LCD_D6, True)
      if bits&0x08==0x08:
        GPIO.output(LCD_D7, True)
     
      # Toggle 'Enable' pin
      lcd_toggle_enable()
     
    def lcd_toggle_enable():
      # Toggle enable
      time.sleep(E_DELAY)
      GPIO.output(LCD_E, True)
      time.sleep(E_PULSE)
      GPIO.output(LCD_E, False)
      time.sleep(E_DELAY)
     
    def lcd_string(message,line,style):
      # Send string to display
      # style=1 Left justified
      # style=2 Centred
      # style=3 Right justified
     
      if style==1:
        message = message.ljust(LCD_WIDTH," ")
      elif style==2:
        message = message.center(LCD_WIDTH," ")
      elif style==3:
        message = message.rjust(LCD_WIDTH," ")
     
      lcd_byte(line, LCD_CMD)
     
      for i in range(LCD_WIDTH):
        lcd_byte(ord(message[i]),LCD_CHR)
     
    ## function for testing the per command line specified configuration file
    def checkImportFile(self):
        ## does the file exist?
        try:
            inifile = open(str(arguments['--inifile']),'r').close()
            data.inifilename = str(arguments['--inifile'])
        except:
            ## if we have a GUI display an error dialog
            try:
                showerror('Import Error','The specified configuration file was not found.')
                return
            except: ## if no GUI display error and exit
                print('Configuration file error. A file with that name seems not to exist, please check.')
                exit()
        try:
            inout.readImportFile()
        except:
            try:
                showerror('Import Error','Could not read the configuration file. Please check file path and/or file.')
                return
            except:
                print 'Could not read configuration file. Please check file path and/or file.'
                exit()

    ## function for acually reading input configuration file
    def readImportFile(self):
        ## read config data from file
        import ConfigParser
        Config = ConfigParser.SafeConfigParser()
        ## read the config file
        Config.read(data.inifilename)
        data.ipaddress     = Config.get('CommSettings','IP address')
        data.portno        = int(Config.get('CommSettings','port number'))
        data.modbusid      = int(Config.get('CommSettings','Modbus ID'))
        data.manufacturer  = Config.get('CommSettings','manufacturer')
        data.loginterval   = int(Config.get('CommSettings','logger interval'))
        try: ## logfilename may be empty. if so data will printed to terminal
            data.logfilename   = Config.get('FileSettings','log file')
        except:
            data.logfilename = None
        data.logmaxbuffer  = int(Config.get('FileSettings','log buffer'))
        data.datasets      = eval(Config.get('TargetDataSettings','data table'))

    ## function for actually writing configuration data
    #
    def writeExportFile(self):
        ## use ini file capabilities
        import ConfigParser
        Config = ConfigParser.ConfigParser()

        ## if the dialog was closed with no file selected ('cancel') just return
        if (data.inifilename == None):
            try: ## if running in command line no window can be displayed
                showerror('Configuration File Error','no file name given, please check.')
            except:
                print('Configuration file error, no file name given, please check.')
            return
        ## write the data to the selected config file
        try:
            inifile = open(data.inifilename,'w')
        except:
            try: ## if running in command line no window can be displayed
                showerror('Configuration File Error','a file with that name seems not to exist, please check.')
            except:
                print('Configuration file error, a file with that name seems not to exist, please check.')
            gui.selectExportFile()
            return

        ## format the file structure
        Config.add_section('CommSettings')
        Config.set('CommSettings','IP address',data.ipaddress)
        Config.set('CommSettings','port number',data.portno)
        Config.set('CommSettings','Modbus ID',data.modbusid)
        Config.set('CommSettings','manufacturer',data.manufacturer)
        Config.set('CommSettings','logger interval',data.loginterval)
        Config.add_section('FileSettings')
        Config.set('FileSettings','log file',data.logfilename)
        Config.set('FileSettings','log buffer',data.logmaxbuffer)
        Config.add_section('TargetDataSettings')
        Config.set('TargetDataSettings','data table',data.datasets)
        
        Config.write(inifile)
        inifile.close()

    ## function for writing to LCD
    #
    def writeLoggerDataLCD(self):

        thisdate = str(datetime.date.today())

        ## check if the file is empty, if so write the header information to the file
        if os.stat(thislogfile).st_size==0:
            with open(thislogfile,'ab') as logfile:
                logwriter = csv.writer(logfile, quoting=csv.QUOTE_ALL)
                ## ensure UTF8 encoding while writing
                ## print out what data is contained and whats its format
                for thisrow in data.datasets:
                    thisrow = [s.encode('utf-8') for s in thisrow]
                    logwriter.writerows([thisrow])

                logfile.write('-'*50+'\n') ## write a separator
                ## format the column headers
                columnheader = 'time'
                for thisrow in data.datasets[1:]: ## omit first row containing 'address'
                    ## ensure UTF8 encoding while writing, since this is the column heading
                    #  no problem with converting to string even if stored as int
                    thisrow = [s.encode('utf-8') for s in thisrow]
                    ## use description field for columnheader if filled
                    if (thisrow[3] != ''):
                        thisdescription = ','+str(thisrow[3])
                        ## if a unit is entered add it after the description
                        if (thisrow[4] != ''):
                            thisdescription += ' ('+str(thisrow[4])+')'
                        columnheader += thisdescription
                    else: ## no description, use address as header
                        columnheader += ', '+str(thisrow[0])

                columnheader += '\n' ## line break before data rows
                logfile.write(columnheader)
        
        ## if the file is not empty we assume an append write to the file
        if len(data.datawritebuffer) > 0: ## if the buffer has data write this to disk
            with open(thislogfile,'ab') as logfile:
                logwriter = csv.writer(logfile)
                logwriter.writerows(data.datawritebuffer)
                data.datawritebuffer = [] ## empty buffer
        else: ## we asume that this was called outside the poll loop with buffer size not reached
            with open(thislogfile,'ab') as logfile:
                logwriter = csv.writer(logfile)
                logwriter.writerows(data.databuffer)
                data.databuffer = [] ## empty buffer

    ## function for starting communication with target
    #
    def runCommunication(self):
        from pymodbus.client.sync import ModbusTcpClient as ModbusClient

        self.client = ModbusClient(host=data.ipaddress, port=data.portno)
        try:
            self.client.connect()
        except:
            showerror('Modbus Connection Error','could not connect to target. Check your settings, please.')
        
        self.pollTargetData()

        self.client.close()
        ## lambda: is required to not spawn hundreds of threads but only one that calls itself
        self.commtimer = Timer(data.loginterval, lambda: self.runCommunication())
        self.commtimer.start() ## needs to be a separate command else the timer is not cancel-able

    def stopCommunication(self):
        #print ('Stopped Communication')
        self.commtimer.cancel()
        ## flush data buffer to disk
        self.writeLoggerDataFile()
    
    ## function for polling data from the target and triggering writing to log file if set
    #
    def pollTargetData(self):
        from pymodbus.payload import BinaryPayloadDecoder
        from pymodbus.constants import Endian
        import datetime

        data.datavector = [] ## empty datavector for current values

        ## request each register from datasets, omit first row which contains only column headers
        for thisrow in data.datasets[1:]:
            ## if the connection is somehow not possible (e.g. target not responding)
            #  show a error message instead of excepting and stopping
            try:
                received = self.client.read_input_registers(address = int(thisrow[0]),
                                                     count = data.moddatatype[thisrow[1]],
                                                      unit = data.modbusid)
            except:
                thisdate = str(datetime.datetime.now()).partition('.')[0]
                thiserrormessage = thisdate + ': Connection not possible. Check settings or connection.'
                if (gui_active):
                    showerror('Connection Error',thiserrormessage)
                    return  ## prevent further execution of this function
                else:
                    print thiserrormessage
                    return  ## prevent further execution of this function

            message = BinaryPayloadDecoder.fromRegisters(received.registers, endian=Endian.Big)
            ## provide the correct result depending on the defined datatype
            if thisrow[1] == 'S32':
                interpreted = message.decode_32bit_int()
            elif thisrow[1] == 'U32':
                interpreted = message.decode_32bit_uint()
            elif thisrow[1] == 'U64':
                interpreted = message.decode_64bit_uint()
            elif thisrow[1] == 'STR32':
                interpreted = message.decode_string(32)
            elif thisrow[1] == 'S16':
                interpreted = message.decode_16bit_int()
            elif thisrow[1] == 'U16':
                interpreted = message.decode_16bit_uint()
            else: ## if no data type is defined do raw interpretation of the delivered data
                interpreted = message.decode_16bit_uint()

            ## check for "None" data before doing anything else
            if ((interpreted == self.MIN_SIGNED) or (interpreted == self.MAX_UNSIGNED)):
                displaydata = None
            else:
                ## put the data with correct formatting into the data table
                if thisrow[2] == 'FIX3':
                    displaydata = float(interpreted) / 1000
                elif thisrow[2] == 'FIX2':
                    displaydata = float(interpreted) / 100
                elif thisrow[2] == 'FIX1':
                    displaydata = float(interpreted) / 10
                else:
                    displaydata = interpreted

            ## save _scaled_ data in datavector for further handling
            data.datavector.append(displaydata)

        ## display collected data
        if (gui_active == 1):
            gui.updateLoggerDisplay()

        ## for logging purposes we need a time stamp first
        stampedvector = []
        ## we don't need the microseconds of the date return value, so we strip it
        stampedvector.append(str(datetime.datetime.now()).partition('.')[0])
        stampedvector += data.datavector
        data.databuffer.append(stampedvector)
        #print data.databuffer
        ## ## is the buffer large enough to be written to file system?
        ## if (len(data.databuffer) >= data.logmaxbuffer):
        ## ensure that the data to write will not be altered by faster poll cycles
        data.datawritebuffer = data.databuffer
        data.databuffer = [] ## empty the buffer
        self.writeLoggerDataLCD() ## call write routine to save data on disk

    ## function adds dataset to the datasets list
    #   also updates the displayed list
    #   new datasets are not added to the config file
    #
    def addDataset(self,inputdata):
        data.datasets.append(inputdata)
        print 'Current datasets: ',(data.datasets)

    ## function for saving program state at program exit
    #
    def cleanOnExit(self):
        try: ## stop data logging on exit, catch a possible exception, when communication is not running
            self.stopCommunication()
        except:
            print ''

        ## if data is available, write polled data from buffer to disk
        if len(data.databuffer):
            self.writeLoggerDataFile()
        print 'PyModMonLCD has exited cleanly.'

    ## function for printing the current configuration settings
    #   only used for debug purpose
    #
    def printConfig(self):
        counter = 0
        for data in data.datasets:
            print('Datasets in List:', counter, data)
            counter += 1

## class that contains all GUI specifics
#
class Gui:
    def __init__(self,master):

        ## configure app window
        master.title('Python Modbus Monitor LCD')
        master.minsize(width=550, height=450)
        master.geometry("550x550")  ## scale window a bit bigger for more data lines
        self.settingscanvas = Canvas(master,bg="yellow",highlightthickness=0)
        self.settingscanvas.pack(side='top',anchor='nw',expand=False,fill='x')

        ## make the contents of settingscanvas fit the window width
        Grid.columnconfigure(self.settingscanvas,0,weight = 1)

        ## create window containers

        ## frame for the config file and data logger file display
        filesframe = Frame(self.settingscanvas,bd=1,relief='groove')
        filesframe.columnconfigure(1,weight=1) ## set 2nd column to be auto-stretched when window is resized
        filesframe.grid(sticky = 'EW')

        ## frame for the settings of the communication parameters
        self.settingsframe = Frame(self.settingscanvas,bd=1,relief='groove')
        self.settingsframe.grid(sticky = 'EW')

        ## frame for the controls for starting and stopping configuration
        controlframe = Frame(self.settingscanvas,bd=1,relief='groove')
        controlframe.grid(sticky = 'EW')

        ## create Menu
        menubar = Menu(master)
        filemenu = Menu(menubar, tearoff=0)
        filemenu.add_command(label='Import Configuration File…',command=self.selectImportFile)
        filemenu.add_command(label='Export Configuration File…',command=self.selectExportFile)
        filemenu.add_command(label='Set Logger Data File…',command=self.selectLoggerDataFile)
        filemenu.add_command(label='Save Current Configuration',command=inout.writeExportFile)
        filemenu.add_command(label='Exit',command=self.closeWindow)

        toolmenu = Menu(menubar, tearoff=0)
        toolmenu.add_command(label='Data Settings…',command=self.dataSettings)
        toolmenu.add_command(label='Print Config Data',command=inout.printConfig)
        
        helpmenu = Menu(menubar, tearoff=0)
        helpmenu.add_command(label='About…',command=self.aboutDialog)
        
        menubar.add_cascade(label='File', menu=filemenu)
        menubar.add_cascade(label='Tools', menu=toolmenu)
        menubar.add_cascade(label='Help', menu=helpmenu)
        master.config(menu=menubar)

        ## add GUI elements

        ## input mask for configuration file
        #
        Label(filesframe, text='Configuration File:').grid(row=0,sticky='E')

        self.input_inifilename = Entry(filesframe, width = 40)
        self.input_inifilename.bind('<Return>',self.getInputFile)   ## enable file name to be set by [Enter] or [Return]
        self.input_inifilename.grid(row=0,column=1,sticky='EW')     ## make input field streching with window
        
        Button(filesframe,text='…',command=(self.selectImportFile)).grid(row=0,column=2,sticky='W') ## opens dialog to choose file from

        Button(filesframe,text='⟲ Re-Read Configuration', command=(self.displaySettings)).grid(row=3,column=0,sticky='W') ## triggers re-read of the configuration file
        Button(filesframe,text='⤓ Save Current Configuration', command=(inout.writeExportFile)).grid(row=3,column=1,sticky='W') ## triggers re-read of the configuration file

        ## buttons for starting and stopping data retrieval from the addressed target
        #

        ## Button for starting communication and starting writing to logger file
        self.commButton = Button(controlframe,text='▶ Start Communication',bg='lightblue', command=self.startCommunication)
        self.commButton.grid(row=0,column=1,sticky='W') 

        ## fields for configuring the data connection
        #
        Label(self.settingsframe, text='Communication Connection Settings', font='-weight bold').grid(columnspan=4, sticky='W')
        Label(self.settingsframe, text='Current Values').grid(row=1,column=1)
        Label(self.settingsframe, text='New Values').grid(row=1,column=2)

        Label(self.settingsframe, text='Target IP Address:').grid(row=2,column=0,sticky = 'E')
        Label(self.settingsframe, text='Port No.:').grid(row=3,column=0,sticky = 'E')
        Label(self.settingsframe, text='Modbus Unit ID:').grid(row=4,column=0,sticky = 'E')
        Label(self.settingsframe, text='Manufacturer:').grid(row=5,column=0,sticky = 'E')
        Label(self.settingsframe, text='Log Interval[s]:').grid(row=6,column=0,sticky = 'E')
        Button(self.settingsframe,text='⮴ Update Settings',bg='lightgreen',command=(self.updateCommSettings)).grid(row=7,column=2, sticky='W')

        ## frame for entering and displaying the data objects
        self.datasettingsframe = Frame(self.settingscanvas,bd=1,relief='groove')
        self.datasettingsframe.columnconfigure(3,weight=1) ## make description field fit the window
        self.datasettingsframe.grid(sticky = 'EW')

        ## table with data objects to display and the received data
        Label(self.datasettingsframe, text='Target Data', font='-weight bold').grid(columnspan=4, sticky='W')
        Label(self.datasettingsframe, text='Addr.').grid(row=1,column=0)
        Label(self.datasettingsframe, text='Type').grid(row=1,column=1)
        Label(self.datasettingsframe, text='Format').grid(row=1,column=2)
        Label(self.datasettingsframe, text='Description').grid(row=1,column=3)
        Label(self.datasettingsframe, text='Unit').grid(row=1,column=4)
        self.input_modaddress=Entry(self.datasettingsframe,width=7)
        self.input_modaddress.grid(row=2,column=0)

        self.input_moddatatype = StringVar()
        self.input_moddatatype.set(list(data.moddatatype.keys())[0])#[0])
        self.choice_moddatatype=OptionMenu(self.datasettingsframe,self.input_moddatatype,*data.moddatatype)
        self.choice_moddatatype.grid(row=2,column=1)

        self.input_dataformat = StringVar()
        self.input_dataformat.set(None)
        self.choice_moddatatype=OptionMenu(self.datasettingsframe,self.input_dataformat,*data.dataformat)
        self.choice_moddatatype.grid(row=2,column=2)

        self.input_description=Entry(self.datasettingsframe,width=35)
        self.input_description.grid(row=2,column=3,sticky='ew')

        self.input_dataunit=Entry(self.datasettingsframe,width=5)
        self.input_dataunit.grid(row=2,column=4)

        Button(self.datasettingsframe,text='+',font='-weight bold',bg='lightyellow',command=(self.addNewDataset)).grid(row=2,column=6)
        
        ## checkbutton to enable manipulation of the entered data.
        #  this is slow, therefore not enabled by default. Also it alters the display layout.
        self.checked_manage = IntVar()
        self.checkManageData=Checkbutton(self.datasettingsframe,
                                         text='Manage data sets',
                                         variable=self.checked_manage,
                                         command=self.displayDatasets,
                                         )
        self.checkManageData.grid(row=3,column=0,columnspan=3)

        ## canvas for displaying monitored data
        self.datacanvas = Canvas(master,bd=1,bg="green",highlightthickness=0)
        self.datacanvas.pack(anchor='sw',side='top',expand=True,fill='both')
        ## frame that holds all data to display. the static data table and the polled data
        self.dataframe = Frame(self.datacanvas)
        self.dataframe.pack(side='left',expand=True,fill='both')
        ## frame for static data table
        self.datadisplayframe = Frame(self.dataframe,bd=1,relief='groove')
        #self.datadisplayframe = Frame(self.datacanvas,bd=1,relief='groove')
        self.datadisplayframe.pack(side='left', anchor='nw',expand=True,fill='both')
        ## frame for data from target
        self.targetdataframe = Frame(self.dataframe,bg='white',relief='groove',bd=1)
        self.targetdataframe.pack(side='left', anchor='nw',expand=True,fill='both')
        #self.targetdataframe.grid(column=1, row=0)
        ## add scrollbar for many data rows
        self.datascrollbar = Scrollbar(self.datacanvas, orient='vertical', command=self.datacanvas.yview)
        self.datascrollbar.pack(side='right',fill='y')
        #self.datascrollbar = Scrollbar(self.datacanvas, orient='vertical', command=self.datacanvas.yview)
        self.datacanvas.configure(yscrollcommand=self.datascrollbar.set)

        ## make data table fit in scrollable frame
        self.datacanvas.create_window((0,0), window=self.dataframe, anchor='nw',tags='dataframe')

        ## fill the datafields with the current settings
        self.displayCommSettings()
        self.displayDatasets()

        self.update_data_layout()

    ## function for updating the data view after adding content to make the scrollbar work correctly
    def update_data_layout(self):
        self.dataframe.update_idletasks()
        self.datacanvas.configure(scrollregion=self.datacanvas.bbox('all'))
        

    def displaySettings(self):
        ## read import file and update displayed data
        inout.readImportFile()
        self.displayCommSettings()
        self.displayDatasets()

        ## update logfile display
        self.input_logfilename.delete(0,END)
        self.input_logfilename.insert(0,data.logfilename)

        ## update displayed filename in entry field
        self.input_inifilename.delete(0,END)
        self.input_inifilename.insert(0,data.inifilename)

    def displayDatasets(self):
        ## display all currently available datasets
        for widget in self.datadisplayframe.winfo_children():
            widget.destroy()

        if (self.checked_manage.get()):
            Label(self.datadisplayframe,text='Up').grid(row=0,column=0)
            Label(self.datadisplayframe,text='Down').grid(row=0,column=1)
            Label(self.datadisplayframe,text='Delete').grid(row=0,column=2)

        thisdata = '' ## make local variable known
        for thisdata in data.datasets:
            counter = data.datasets.index(thisdata) ## to keep track of the current row
            if (self.checked_manage.get()):
                ## add some buttons to change order of items and also to delete them
                if (counter > 1): ## first dataset cannot be moved up
                    buttonUp=Button(self.datadisplayframe,
                                    text='↑',
                                    command=lambda i=counter:(self.moveDatasetUp(i)))
                    buttonUp.grid(row=(counter),column = 0)
                if ((counter > 0) and (counter != (len(data.datasets)-1))): ## last dataset cannot be moved down
                    buttonDown=Button(self.datadisplayframe,
                                      text='↓',
                                      command=lambda i=counter:(self.moveDatasetDown(i)))
                    buttonDown.grid(row=(counter),column = 1)
                if (counter > 0): ## do not remove dataset [0]
                    buttonDelete=Button(self.datadisplayframe,
                                        text='-',
                                        command=lambda i=counter:(self.deleteDataset(i)))
                    buttonDelete.grid(row=(counter),column = 2)

            ## add the currently stored data for the dataset
            Label(self.datadisplayframe,width=3,text=counter).grid(row=(counter),column=3)
            Label(self.datadisplayframe,width=6,text=thisdata[0]).grid(row=(counter),column=4)
            Label(self.datadisplayframe,width=7,text=thisdata[1]).grid(row=(counter),column=5)
            Label(self.datadisplayframe,width=7,text=thisdata[2]).grid(row=(counter),column=6)
            Label(self.datadisplayframe,width=25,text=thisdata[3]).grid(row=(counter),column=7,sticky='ew')
            Label(self.datadisplayframe,width=6,text=thisdata[4]).grid(row=(counter),column=8)

        self.update_data_layout()
   
    ## reorder the datasets, move current dataset one up
    def moveDatasetUp(self,current_position):
        i = current_position
        data.datasets[i], data.datasets[(i-1)] = data.datasets[(i-1)], data.datasets[i]
        self.displayDatasets()

    ## reorder the datasets, move current dataset one down
    def moveDatasetDown(self,current_position):
        i = current_position
        data.datasets[i], data.datasets[(i+1)] = data.datasets[(i+1)], data.datasets[i]
        self.displayDatasets()

    ## reorder the datasets, delete the current dataset
    def deleteDataset(self,current_position):
        i = current_position
        del data.datasets[i]
        self.displayDatasets()

    def displayCommSettings(self):
        self.current_ipaddress = Label(self.settingsframe, text=data.ipaddress, bg='white')
        self.current_ipaddress.grid (row=2,column=1,sticky='EW')
        self.input_ipaddress = Entry(self.settingsframe, width=15, fg='blue')
        self.input_ipaddress.grid(row=2,column=2, sticky = 'W') # needs to be on a separate line for variable to work
        self.input_ipaddress.bind('<Return>',self.updateCommSettings) ## enable the Entry to update without button click

        self.current_portno = Label(self.settingsframe, text=data.portno, bg='white')
        self.current_portno.grid (row=3,column=1,sticky='EW')
        self.input_portno = Entry(self.settingsframe, width=5, fg='blue')
        self.input_portno.grid(row=3,column=2, sticky = 'W')
        self.input_portno.bind('<Return>',self.updateCommSettings) ## update without button click

        self.current_modbusid = Label(self.settingsframe, text=data.modbusid, bg='white')
        self.current_modbusid.grid (row=4,column=1,sticky='EW')
        self.input_modbusid = Entry(self.settingsframe, width=5, fg='blue')
        self.input_modbusid.grid(row=4,column=2, sticky = 'W')
        self.input_modbusid.bind('<Return>',self.updateCommSettings) ## update without button click

        self.current_manufacturer = Label(self.settingsframe, text=data.manufacturer, bg='white')
        self.current_manufacturer.grid (row=5,column=1,sticky='EW')
        self.input_manufacturer = Entry(self.settingsframe, width=25, fg='blue')
        self.input_manufacturer.grid(row=5,column=2, sticky = 'W')
        self.input_manufacturer.bind('<Return>',self.updateCommSettings) ## update without button click

        self.current_loginterval = Label(self.settingsframe, text=data.loginterval, bg='white')
        self.current_loginterval.grid (row=6,column=1,sticky='EW')
        self.input_loginterval = Entry(self.settingsframe, width=3, fg='blue')
        self.input_loginterval.grid(row=6,column=2, sticky = 'W')
        self.input_loginterval.bind('<Return>',self.updateCommSettings) ## update without button click
        
    ## function for updating communication parameters with input sanitation
    #  if no values are given in some fields the old values are preserved
    #
    def updateCommSettings(self,*args):

        #print('update Communication Settings:')
        if self.input_ipaddress.get() != '':
            thisipaddress = unicode(self.input_ipaddress.get())
            ## test if the data seems to be a valid IP address
            try:
                self.ip_address(thisipaddress)
                data.ipaddress = unicode(self.input_ipaddress.get())
            except:
                showerror('IP Address Error','the data you entered seems not to be a correct IP address')
            ## if valid ip address entered store it

        if self.input_portno.get() != '':
            ## test if the portnumber seems to be a valid value
            try:
                check_portno = int(self.input_portno.get())
                if check_portno < 0:
                    raise ValueError
            except ValueError:
                showerror('Port Number Error','the value you entered seems not to be a valid port number')
                return
            data.portno = int(self.input_portno.get())

        if self.input_modbusid.get() != '':
            ## test if the modbus ID seems to be a valid value
            try:
                check_modbusid = int(self.input_portno.get())
                if check_modbusid < 0:
                    raise ValueError
            except ValueError:
                showerror('Port Number Error','the value you entered seems not to be a valid Modbus ID')
                return
            data.modbusid = int(self.input_modbusid.get())

        if self.input_manufacturer.get() != '':
            data.manufacturer = (self.input_manufacturer.get())

        if self.input_loginterval.get() != '':
            ## test if the logger intervall seems to be a valid value
            try:
                check_loginterval = int(self.input_loginterval.get())
                if check_loginterval < 1:
                    raise ValueError
            except ValueError:
                showerror('Logger Interval Error','the value you entered seems not to be a valid logger intervall')
                return
            data.loginterval = int(self.input_loginterval.get())

        self.displayCommSettings()

    ## function for starting communication and changing button function and text
    #
    def startCommunication(self):
        inout.runCommunication()
        self.commButton.configure(text='⏹ Stop Communication',bg='red', command=(self.stopCommunication))

    def stopCommunication(self):
        inout.stopCommunication()
        self.commButton.configure(text='▶ Start Communication',bg='lightblue', command=(self.startCommunication))

    ## function for reading configuration file
    #
    def selectImportFile(self):
        data.inifilename = askopenfilename(title = 'Choose Configuration File',defaultextension='.ini',filetypes=[('Configuration file','*.ini'), ('All files','*.*')])

        ## update displayed filename in entry field
        self.input_inifilename.delete(0,END)
        self.input_inifilename.insert(0,data.inifilename)

        self.displaySettings()

    ## function for checking for seemingly correct IP address input
    #
    def ip_address(self,address):
        valid = address.split('.')
        if len(valid) != 4:
            raise ValueError
        for element in valid:
            if not element.isdigit():
                raise ValueError
                break
            i = int(element)
            if i < 0 or i > 255:
                raise ValueError
        return

    ## function for selecting configuration export file
    #
    def selectExportFile(self):
        data.inifilename = asksaveasfilename(initialfile = data.inifilename,
                                                  title = 'Choose Configuration File',
                                                  defaultextension='.ini',
                                                  filetypes=[('Configuration file','*.ini'), ('All files','*.*')])

        ## update displayed filename in entry field
        self.input_inifilename.delete(0,END)
        self.input_inifilename.insert(0,data.inifilename)

        inout.writeExportFile()

    ## function for updating the current received data on display
    #
    def updateLoggerDisplay(self):
        thisdata = '' ## make variable data known
        ## delete old data
        for displayed in self.targetdataframe.winfo_children():
            displayed.destroy()
        ## display new data
        Label(self.targetdataframe,text='Value').grid(row=0,column=0)
        for thisdata in data.datavector:
            ## send data to display table
            Label(self.targetdataframe,text=thisdata,bg='white').grid(column=0,sticky='e')

    ## function for setting program preferences (if needed)
    #
    def dataSettings(self):
        print('dataSettings')

    ## function for updating the configuration file
    #   with the path entered into the text field
    #
    def getInputFile(self,event):
        data.inifilename = event.widget.get()

    ## function adds dataset to the datasets list
    #   also updates the displayed list
    #   new datasets are not added to the config file
    #
    def addNewDataset(self):
        inout.addDataset([self.input_modaddress.get(),
                          self.input_moddatatype.get(),
                          self.input_dataformat.get(),
                          self.input_description.get(),
                          self.input_dataunit.get()])
        self.displayDatasets()
        #print (data.datasets)

    ## function for displaying the about dialog
    #
    def aboutDialog(self):
        showinfo('About Python Modbus Monitor'\
                 ,'This is a program that acts as a modbus slave to receive data from modbus masters like SMA solar inverters. \nYou can choose the data to be received via the GUI and see the live data. \nYou can also call the programm from the command line with a configuration file given for the data to be retrieved. \nThe configuration file can be generated using the GUI command \"File\"→\"Export Configuration\"')
        
    ## function for closing the program window
    #
    def closeWindow(self):
        exit()

## create a data object
data = Data()

## create an input output object
inout = Inout()

## what to do on program exit
atexit.register(inout.cleanOnExit)

## create main program window
## if we are in command line mode lets detect it
gui_active = 0
if (arguments['--nogui'] == False):
    ## load graphical interface library
    from Tkinter import *
    from tkMessageBox import *
    from tkFileDialog import *
    try: ## if the program was called from command line without parameters
        window = Tk()
        ## create window container
        gui = Gui(window)
        gui_active = 1
        if (arguments['--inifile'] != None):
            inout.checkImportFile()
            gui.displaySettings()
    
        mainloop()
        exit() ## if quitting from GUI do not proceed further down to command line handling
    except TclError:
        ## check if one of the required command line parameters is set
        if ((arguments['--inifile'] == None) and (arguments['--ip'] == None)):
            print 'Error. No graphical interface found. Try "python pymodmon.py -h" for help.'
            exit()
        ## else continue with command line execution

########     this section handles all command line logic    ##########################

## read the configuration file
if (arguments['--inifile'] != None):
    inout.checkImportFile()

## get log interval value and check for valid value
if (arguments['--loginterval'] != None):
    try:
        check_loginterval = int(arguments['--loginterval'])
        if check_loginterval < 1:
            raise ValueError
    except ValueError:
        print('Log interval error. The interval must be 1 or more.')
        exit()
    data.loginterval = int(arguments['--loginterval'])

## get all values for single-value reads
## all obligatory entries. missing entries will be caught by docopt.
#  only simple checks will be done, because if there are errors, communication will fail.
if (arguments['--ip'] != None): ## just a check for flow logic, skipped when working with inifile
    data.ipaddress = str(arguments['--ip'])
    data.modbusid = int(arguments['--id'])
    data.port = int(arguments['--port'])
    ## because called from command line data.datasets has only one entry
    #  we can just append and use same mechanics as in "normal" mode
    data.datasets.append( [int(arguments['--addr']),
                           str(arguments['--type']),
                           str(arguments['--format']),
                           str(arguments['--descr']),
                           str(arguments['--unit']) ] )

if (arguments['--lcdl'] != None): ## just a check for flow logic, skipped when working with inifile
    try:
        check_lcdline = int(arguments['--lcdl'])
        if ((check_lcdline < 1) or (check_lcdline > 4)):
            raise ValueError
    except ValueError:
        print('LCD line error. The line must be between 1 and 4.')
        exit()
    inout.lcd_line = int(arguments['--lcdl'])

if (arguments['--lcdc'] != None): ## just a check for flow logic, skipped when working with inifile
    try:
        check_lcdcolumn = int(arguments['--lcdc'])
        if ((check_lcdcolumn < 1) or (check_lcdcolumn > 4)):
            raise ValueError
    except ValueError:
        print('LCD line error. The line must be between 1 and 4.')
        exit()
    inout.lcd_column = int(arguments['--lcdc'])

## start polling data
## single poll first
inout.runCommunication()
## if --single is set, exit immediately
if (arguments['--single'] == True):
    inout.stopCommunication()
    print 'single run'
    exit()

    
#!/usr/bin/python
#--------------------------------------
#    ___  ___  _ ____
#   / _ \/ _ \(_) __/__  __ __
#  / , _/ ___/ /\ \/ _ \/ // /
# /_/|_/_/  /_/___/ .__/\_, /
#                /_/   /___/
#
#  lcd_16x2.py
#  20x4 LCD Test Script with
#  backlight control and text justification
#
# Author : Matt Hawkins
# Date   : 06/04/2015
#
# http://www.raspberrypi-spy.co.uk/
#
#--------------------------------------
 
# The wiring for the LCD is as follows:
# 1 : GND
# 2 : 5V
# 3 : Contrast (0-5V)*
# 4 : RS (Register Select)
# 5 : R/W (Read Write)       - GROUND THIS PIN
# 6 : Enable or Strobe
# 7 : Data Bit 0             - NOT USED
# 8 : Data Bit 1             - NOT USED
# 9 : Data Bit 2             - NOT USED
# 10: Data Bit 3             - NOT USED
# 11: Data Bit 4
# 12: Data Bit 5
# 13: Data Bit 6
# 14: Data Bit 7
# 15: LCD Backlight +5V**
# 16: LCD Backlight GND
 
#import
import RPi.GPIO as GPIO
import time
 
# Define GPIO to LCD mapping
LCD_RS = 7
LCD_E  = 8
LCD_D4 = 25
LCD_D5 = 24
LCD_D6 = 23
LCD_D7 = 18
 
# Define some device constants
LCD_WIDTH = 20    # Maximum characters per line
LCD_CHR = True
LCD_CMD = False
 
LCD_LINE_1 = 0x80 # LCD RAM address for the 1st line
LCD_LINE_2 = 0xC0 # LCD RAM address for the 2nd line
LCD_LINE_3 = 0x94 # LCD RAM address for the 3rd line
LCD_LINE_4 = 0xD4 # LCD RAM address for the 4th line
 
# Timing constants
E_PULSE = 0.0005
E_DELAY = 0.0005
 
def main():
  # Main program block
 
  # Initialise display
  lcd_init()
 
  while True:
 
    # Send some centred test
    lcd_string("--------------------",LCD_LINE_1,2)
    lcd_string("Rasbperry Pi",LCD_LINE_2,2)
    lcd_string("Model B",LCD_LINE_3,2)
    lcd_string("--------------------",LCD_LINE_4,2)
 
    time.sleep(3) # 3 second delay
 
    lcd_string("Raspberrypi-spy",LCD_LINE_1,3)
    lcd_string(".co.uk",LCD_LINE_2,3)
    lcd_string("",LCD_LINE_3,2)
    lcd_string("20x4 LCD Module Test",LCD_LINE_4,2)
 
    time.sleep(3) # 20 second delay
 
    # Blank display
    lcd_byte(0x01, LCD_CMD)
 
    time.sleep(3) # 3 second delay
 
def lcd_init():
  # LCD interface setup
  GPIO.setmode(GPIO.BCM)       # Use BCM GPIO numbers
  GPIO.setup(LCD_E, GPIO.OUT)  # E
  GPIO.setup(LCD_RS, GPIO.OUT) # RS
  GPIO.setup(LCD_D4, GPIO.OUT) # DB4
  GPIO.setup(LCD_D5, GPIO.OUT) # DB5
  GPIO.setup(LCD_D6, GPIO.OUT) # DB6
  GPIO.setup(LCD_D7, GPIO.OUT) # DB7
 
  # Initialise display
  lcd_byte(0x33,LCD_CMD) # 110011 Initialise
  lcd_byte(0x32,LCD_CMD) # 110010 Initialise
  lcd_byte(0x06,LCD_CMD) # 000110 Cursor move direction
  lcd_byte(0x0C,LCD_CMD) # 001100 Display On,Cursor Off, Blink Off
  lcd_byte(0x28,LCD_CMD) # 101000 Data length, number of lines, font size
  lcd_byte(0x01,LCD_CMD) # 000001 Clear display
  time.sleep(E_DELAY)
 
def lcd_byte(bits, mode):
  # Send byte to data pins
  # bits = data
  # mode = True  for character
  #        False for command
 
  GPIO.output(LCD_RS, mode) # RS
 
  # High bits
  GPIO.output(LCD_D4, False)
  GPIO.output(LCD_D5, False)
  GPIO.output(LCD_D6, False)
  GPIO.output(LCD_D7, False)
  if bits&0x10==0x10:
    GPIO.output(LCD_D4, True)
  if bits&0x20==0x20:
    GPIO.output(LCD_D5, True)
  if bits&0x40==0x40:
    GPIO.output(LCD_D6, True)
  if bits&0x80==0x80:
    GPIO.output(LCD_D7, True)
 
  # Toggle 'Enable' pin
  lcd_toggle_enable()
 
  # Low bits
  GPIO.output(LCD_D4, False)
  GPIO.output(LCD_D5, False)
  GPIO.output(LCD_D6, False)
  GPIO.output(LCD_D7, False)
  if bits&0x01==0x01:
    GPIO.output(LCD_D4, True)
  if bits&0x02==0x02:
    GPIO.output(LCD_D5, True)
  if bits&0x04==0x04:
    GPIO.output(LCD_D6, True)
  if bits&0x08==0x08:
    GPIO.output(LCD_D7, True)
 
  # Toggle 'Enable' pin
  lcd_toggle_enable()
 
def lcd_toggle_enable():
  # Toggle enable
  time.sleep(E_DELAY)
  GPIO.output(LCD_E, True)
  time.sleep(E_PULSE)
  GPIO.output(LCD_E, False)
  time.sleep(E_DELAY)
 
def lcd_string(message,line,style):
  # Send string to display
  # style=1 Left justified
  # style=2 Centred
  # style=3 Right justified
 
  if style==1:
    message = message.ljust(LCD_WIDTH," ")
  elif style==2:
    message = message.center(LCD_WIDTH," ")
  elif style==3:
    message = message.rjust(LCD_WIDTH," ")
 
  lcd_byte(line, LCD_CMD)
 
  for i in range(LCD_WIDTH):
    lcd_byte(ord(message[i]),LCD_CHR)
 
if __name__ == '__main__':
 
  try:
    main()
  except KeyboardInterrupt:
    pass
  finally:
    lcd_byte(0x01, LCD_CMD)
    lcd_string("Goodbye!",LCD_LINE_1,2)
    GPIO.cleanup()
