# coding=UTF-8

## @package pymodmon
# Python Modbus Monitor
# a small program that uses the pymodbus package to retrieve and
# display modbus slave data.
# requires: Python 2.7, pymodbus, docopt
#
# Date created: 2016-05-04
# Author: André Schieleit (ASc)

'''Python Modbus Monitor.

Usage:
    pymodmon.py
    pymodmon.py [-h|--help]
    pymodmon.py [--version]
    pymodmon.py -i <file>|--inifile=<file> [-l <file>|--logfile=<file>] [-L <sec>|--loginterval=<sec>] [-B <buf>|--logbuffer=<buf>] [-S|--single]
    pymodmon.py --ip=<IP-address> --port=<port> --id=<id> --addr=<adr> --type=<TYPE> --format=<FORM> [-L <sec>|--loginterval=<sec>] [-B <buf>|--logbuffer=<buf>] [--descr=<"descr">] [--unit=<"unit">] [-S|--single] [-l <file>|--logfile=<file>]

Options:
    no options given in a xterm will open the TK interface
    -h, --help            Show this screen
    --version             Show version
    -i, --inifile=<file>  Uses the given file as input for communication and
                          log file settings and channel configuration
    -l, --logfile=<file>  Uses the given file as output for the retrieved data.
                          The data will be formatted in csv.
                          Existing files will be appended.
    --ip=<IP-address>     Use this as the IP address of the communication target
    --port=<port>         Port of the communication target
    --id=<id>             Modbus ID of the communication target
    --addr=<adr>          Address of the modbus register to read
    --type=<TYPE>         Data type of the retrieved data at a given address.
                          Allowed types: U64, U32, U16, S32, S16, STR32
    --format=<FORM>       Format of the retrieved data.
                          Allowed formats: RAW, UTF8, FIX0, FIX1, FIX2, FIX3
    --descr=<descr>     Description for the retrieved data.
                          e.g. -d="device name"
    --unit=<unit>       Unit of the retrieved data. e.g. -u="V"
    -S, --single          Do only one read cycle instead of continuous reading.
    -L, --loginterval=<sec>  Read data every xx seconds. [defaul value: 5]
    -B, --logbuffer=<buf> Read xx datasets before writing to disk.
                          Useful to prevent wearout on solid state devices.
                          [default value: 50]
'''

from docopt import docopt
if __name__ == '__main__':
    arguments = docopt(__doc__, version='PyModMon 1.0')
    #print(arguments)

# load graphical interface library
try:
    # for Python2
    import Tkinter as tk
except ImportError:
    # for Python3
    import tkinter as tk

from Tkinter import *
from tkMessageBox import *
from tkFileDialog import *
try:
    from pymodbus import *
except ImportError:
    try: ## for command line showerror does not work
        showerror('Import Error','pymodbus package was not found on your system.\nPlease install it using the command:\
                                \n"pip install pymodbus"')
    except:
        print ('Import errror. pymodbus package was not found on your system. Please install it using the command: "pip install pymodbus"')
try:
    import docopt
except ImportError:
    try: ## for command line showerror does not work
        showerror('Import Error','docopt package was not found on your system.\nPlease install it using the command:\
                                \n"pip install docopt"')
    except:
        print ('Import errror. docopt package was not found on your system. Please install it using the command: "pip install docopt"')

## enable execution of functions on program exit    
import atexit
## enable timed execution of the data polling
from threading import Timer
## enable file access
import os

## class for all data related things
#
class Data(object):
    def __init__(self):
        self.inifilename = None
        self.logfilename = None
        self.logmaxbuffer = 50 ## how many records will be buffered before writing to file
        self.ipaddress = '10.0.0.42'
        self.portno =   502
        self.modbusid = 3
        self.manufacturer = 'Default Manufacturer' 
        self.loginterval = 5
        self.moddatatype = {
                'S32':2,
                'U32':2,
                'U64':4,
                'STR32':16,
                'S16':1,
                'U16':1
                }

        self.dataformat = ['ENUM','UTF8','FIX3','FIX2','FIX1','FIX0','RAW']

        self.datasets = [['address','type','format','description','unit','value']]

        self.datavector = []    ## holds the polled data from target
        self.databuffer = []    ## holds the datavectors before writing to disk
        self.datawritebuffer = []  ## holds a copy of databuffer for actual writing to disk

## class that contains all IO specifics
class Inout:
    ## function for testing the per command line specified configuration file
    def checkImportFile(self):
        try:
            inifile = open(str(arguments['--inifile']),'r').close()
        except:
            print('Configuration file error. A file with that name seems not to exist, please check.')
            exit()
        data.inifilename = str(arguments['--inifile'])
        try:
            inout.readImportFile()
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

    ## function for writing to log file
    #  checks if it is an existing file with data in it and will append then
    #  this function should only be called in intervals writing data in bulk (e.g. every 5 minutes)
    #  to prevent wearout on solid state disks like SD CARDs
    #
    def writeLoggerDataFile(self):
        import csv
        if (data.logfilename == None): ## when no filename is given, print data to terminal
            if len(data.datawritebuffer) > 0: ## if the buffer has data write this to terminal
                    print (data.datawritebuffer)
                    data.datawritebuffer = [] ## empty buffer
            else: ## we asume that this was called outside the poll loop with buffer size not reached
                    print(data.databuffer)
                    if (len(data.databuffer) == 1): ## if only one address was provided via command line
                        print data.databuffer[0][0],data.datasets[1][3],data.databuffer[0][1],data.datasets[1][4] 
                    data.databuffer = [] ## empty buffer
            return

        ## try to open the file. if it does not exist, create it on the way
        try:
            open(data.logfilename, 'a').close()
        except:
            try: ## if running in command line no window can be displayed
                showerror('Log File Error','file cannot be accessed, please check.')
            except:
                print('Log file error. File cannot be accessed, please check.')
            return


        ## check if the file is empty, if so write the header information to the file
        if os.stat(data.logfilename).st_size==0:
            with open(data.logfilename,'ab') as logfile:
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
            with open(data.logfilename,'ab') as logfile:
                logwriter = csv.writer(logfile)
                logwriter.writerows(data.datawritebuffer)
                data.datawritebuffer = [] ## empty buffer
        else: ## we asume that this was called outside the poll loop with buffer size not reached
            with open(data.logfilename,'ab') as logfile:
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
            received = self.client.read_input_registers(address = int(thisrow[0]),
                                                     count = data.moddatatype[thisrow[1]],
                                                      unit = data.modbusid)
    
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
        stampedvector.append(str(datetime.datetime.now()))
        stampedvector += data.datavector
        data.databuffer.append(stampedvector)
        #print self.data.databuffer
        ## is the buffer large enough to be written to file system?
        if (len(data.databuffer) >= data.logmaxbuffer):
            ## ensure that the data to write will not be altered by faster poll cycles
            data.datawritebuffer = data.databuffer
            data.databuffer = [] ## empty the buffer
            self.writeLoggerDataFile() ## call write routine to save data on disk

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
        #print 'Program was ended.'
        print 'PyModMon has exited cleanly.'
        #TODO: write code that saves last used config file and saves all logger data

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
#!!        #self.data = Data()#,0,0,0,0,0,0) # create data object for this instance

        ## configure app window
        master.title('Python Modbus Monitor')
        master.minsize(width=550, height=450)
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

        ## input mask for data logger file
        #
        Label(filesframe, text='Data Logger File:').grid(row=1,sticky='E')

        self.input_logfilename = Entry(filesframe, width = 40)
        self.input_logfilename.bind('<Return>',self.setLogFile)     ## enable file name to be set by [Enter] or [Return]
        self.input_logfilename.grid(row=1,column=1,sticky='EW')     ## make input field streching with window

        Button(filesframe,text='…',command=(self.selectLoggerDataFile)).grid(row=1,column=2,sticky='W') ## opens dialog to choose file from

        Button(filesframe,text='⟲ Re-Read Configuration', command=(self.displaySettings)).grid(row=2,column=0,sticky='W') ## triggers re-read of the configuration file
        Button(filesframe,text='⤓ Save Current Configuration', command=(inout.writeExportFile)).grid(row=2,column=1,sticky='W') ## triggers re-read of the configuration file

        ## buttons for starting and stopping data retrieval from the addressed target
        #
        Button(controlframe,text='⏹ Stop Communication',bg='red', command=(inout.stopCommunication)).grid(row=0,column=1,sticky='W') ## stops writing to logger file

        Button(controlframe,text='▶ Start Communication',bg='lightblue', command=(inout.runCommunication)).grid(row=0,column=4,sticky='W') ## starts writing to logger file

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
        Label(self.datasettingsframe, text='No.').grid(row=1,column=0)
        Label(self.datasettingsframe, text='Addr.').grid(row=1,column=1)
        Label(self.datasettingsframe, text='Type').grid(row=1,column=2)
        Label(self.datasettingsframe, text='Format').grid(row=1,column=3)
        Label(self.datasettingsframe, text='Description').grid(row=1,column=4)
        Label(self.datasettingsframe, text='Unit').grid(row=1,column=5)
        Label(self.datasettingsframe, text='Value').grid(row=1,column=6)
        self.input_modaddress=Entry(self.datasettingsframe,width=7)
        self.input_modaddress.grid(row=2,column=1)

        self.input_moddatatype = StringVar()
        self.input_moddatatype.set(list(data.moddatatype.keys())[0])#[0])
        self.choice_moddatatype=OptionMenu(self.datasettingsframe,self.input_moddatatype,*data.moddatatype)
        self.choice_moddatatype.grid(row=2,column=2)

        self.input_dataformat = StringVar()
        self.input_dataformat.set(None)
        self.choice_moddatatype=OptionMenu(self.datasettingsframe,self.input_dataformat,*data.dataformat)
        self.choice_moddatatype.grid(row=2,column=3)

        self.input_description=Entry(self.datasettingsframe,width=35)
        self.input_description.grid(row=2,column=4,sticky='ew')

        self.input_dataunit=Entry(self.datasettingsframe,width=5)
        self.input_dataunit.grid(row=2,column=5)

        Button(self.datasettingsframe,text='+',font='-weight bold',bg='lightyellow',command=(self.addNewDataset)).grid(row=2,column=6)

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
        #self.datascrollbar = Scrollbar(self.datacanvas, orient='vertical', command=self.datacanvas.yview)
        self.datacanvas.configure(yscrollcommand=self.datascrollbar.set)
        self.datascrollbar.pack(side='right',fill='y')

        ## make data table fit in scrollable frame
        self.datacanvas.create_window((1,1), window=self.dataframe, anchor='nw',tags='self.dataframe')

        ## fill the datafields with the current settings
        self.displayCommSettings()
        self.displayDatasets()

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

        thisdata = '' ## make local variable known
        for thisdata in data.datasets:
            counter = data.datasets.index(thisdata)
            Label(self.datadisplayframe,width=3,text=counter).grid(row=(3+counter),column=0)
            Label(self.datadisplayframe,width=6,text=thisdata[0]).grid(row=(3+counter),column=1)
            Label(self.datadisplayframe,width=7,text=thisdata[1]).grid(row=(3+counter),column=2)
            Label(self.datadisplayframe,width=7,text=thisdata[2]).grid(row=(3+counter),column=3)
            Label(self.datadisplayframe,width=25,text=thisdata[3]).grid(row=(3+counter),column=4,sticky='ew')
            Label(self.datadisplayframe,width=6,text=thisdata[4]).grid(row=(3+counter),column=5)
   
    def displayCommSettings(self):
        self.current_ipaddress = Label(self.settingsframe, text=data.ipaddress, bg='white')
        self.current_ipaddress.grid (row=2,column=1,sticky='EW')
        self.input_ipaddress = Entry(self.settingsframe, width=15, fg='blue')
        self.input_ipaddress.grid(row=2,column=2, sticky = 'W') # needs to be on a seperate line for variable to work
        self.current_portno = Label(self.settingsframe, text=data.portno, bg='white')
        self.current_portno.grid (row=3,column=1,sticky='EW')
        self.input_portno = Entry(self.settingsframe, width=5, fg='blue')
        self.input_portno.grid(row=3,column=2, sticky = 'W')

        self.current_modbusid = Label(self.settingsframe, text=data.modbusid, bg='white')
        self.current_modbusid.grid (row=4,column=1,sticky='EW')
        self.input_modbusid = Entry(self.settingsframe, width=5, fg='blue')
        self.input_modbusid.grid(row=4,column=2, sticky = 'W')

        self.current_manufacturer = Label(self.settingsframe, text=data.manufacturer, bg='white')
        self.current_manufacturer.grid (row=5,column=1,sticky='EW')
        self.input_manufacturer = Entry(self.settingsframe, width=25, fg='blue')
        self.input_manufacturer.grid(row=5,column=2, sticky = 'W')

        self.current_loginterval = Label(self.settingsframe, text=data.loginterval, bg='white')
        self.current_loginterval.grid (row=6,column=1,sticky='EW')
        self.input_loginterval = Entry(self.settingsframe, width=3, fg='blue')
        self.input_loginterval.grid(row=6,column=2, sticky = 'W')
        
    ## function for updating communication parameters with input sanitation
    #  if no values are given in some fields the old values are preserved
    #
    def updateCommSettings(self):
        try:
            import ipaddress
        except ImportError:
            showerror('Import Error','ipaddress package was not found on your system.\n\
                       Please install it using the command:\
                                \n"pip install ipaddress"')

        #print('update Communication Settings:')
        if self.input_ipaddress.get() != '':
            data.ipaddress = (self.input_ipaddress.get())
            ## test if the data seems to be a valid IP address
            try:
                ipaddress.ip_address(data.ipaddress)
            except:
                showerror('IP Address Error','the data you entered seems not to be a correct IP address')

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

    ## function for reading configuration file
    #
    def selectImportFile(self):
        data.inifilename = askopenfilename(title = 'Choose Configuration File',defaultextension='.ini',filetypes=[('Configuration file','*.ini'), ('All files','*.*')])

        ## update displayed filename in entry field
        self.input_inifilename.delete(0,END)
        self.input_inifilename.insert(0,data.inifilename)

        self.displaySettings()

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

    ## function for choosing logger data file
    #
    def selectLoggerDataFile(self):
        data.logfilename = asksaveasfilename(initialfile = self.data.logfilename, title = 'Choose File for Logger Data', defaultextension='.csv',filetypes=[('CSV file','*.csv'), ('All files','*.*')])
        self.input_logfilename.delete(0,END)
        self.input_logfilename.insert(0,self.data.logfilename)

        ## for logging purposes we need a time stamp first
        stampedvector = []
        stampedvector.append(str(datetime.datetime.now()))
        stampedvector += data.datavector
        data.databuffer.append(stampedvector)
        ## is the buffer large enough to be written to file system?
        if (len(data.databuffer) >= data.logmaxbuffer):
            ## ensure that the data to write will not be altered by faster poll cycles
            data.datawritebuffer = data.databuffer
            data.databuffer = [] ## empty the buffer
            inout.writeLoggerDataFile() ## call write routine to save data on disk

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
        # TODO: add dialog for settings
        print('dataSettings')

    ## function for updating the configuration file
    #   with the path entered into the text field
    #
    def getInputFile(self,event):
        self.data.inifilename = event.widget.get()

    ## function for updating the log file path
    #   with the path entered into the entry field
    #
    def setLogFile(self,event):
        self.data.logfilename = event.widget.get()

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
        #print (self.data.datasets)

    ## function for updating the display window to make the scrollbar fit the content
    #
    def on_configure(self, event):
        w,h = event.width, event. height
        natural = self.dataframe.winfo_reqheight()
        self.datacanvas.itemconfigure('self.dataframe', height=h if (h > natural) else natural)
        self.datacanvas.configure(scrollregion = self.datacanvas.bbox('all'))

    ## function for displaying the about dialog
    #
    def aboutDialog(self):
        showinfo('About Python Modbus Monitor'\
                 ,'This is a program that acts as a modbus master to receive data from modbus slaves like SMA solar inverters. \nYou can choose the data to be recalled via the GUI and see the live data. \nYou can also call the programm from the command line with a configuration file given for the data to be retrieved. \nThe configuration file can be generated using the GUI command \"File\"→\"Export Configuration\"')
        
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
#!!    try:
#!!       inifile = open(str(arguments['--inifile']),'r').close()
#!!    except:
#!!       print('Configuration file error. A file with that name seems not to exist, please check.')
#!!       exit()
#!!    data.inifilename = str(arguments['--inifile'])
#!!    try:
#!!        inout.readImportFile()
#!!    except:
#!!        print 'Could not read configuration file. Please check file path and/or file.'
#!!        exit()

## get log file name and try to access it
if (arguments['--logfile'] != None):
    data.logfilename = str(arguments['--logfile'])
    inout.writeLoggerDataFile() ## initial write to file, tests for file

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

## get log buffer size and check for valid value
if (arguments['--logbuffer'] != None):
    try:
        check_logbuffer = int(arguments['--logbuffer'])
        if check_logbuffer < 1:
            raise ValueError
    except ValueError:
        print('Log buffer error. The log buffer must be 1 or more.')
        exit()
    data.logmaxbuffer = int(arguments['--logbuffer'])

## get all values for single-value reads
## all obligatory entries. missing entries will be caught by docopt.
# only simple checks will be done, because if there are errors, communication will fail.
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

## start polling data
## single poll first
inout.runCommunication()
## if --single is set, exit immediately
if (arguments['--single'] == True):
    inout.stopCommunication()
    print 'single run'
    exit()

## since we start a timer thread for periodic pulling of data we need no "while True:" loop
# for staying in the application
#from time import sleep
#while True:
#    sleep(15)
    
