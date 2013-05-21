#!/usr/bin/python
#-*-coding:utf-8-*-
'''
Created on 18.06.2012

@author: tlehw001
'''

import Tkinter,sys
from floppbox import createDefaultConfig
class ConfigGUI (Tkinter.Frame):
    
    TCP_PORT ='1111'
    BROADCASTINTERVALL = '10'
    TIMEOUT = '10'
    CHUNK_SIZE = '1024'

    
    
    def __init__(self, path, master=None):
            Tkinter.Frame.__init__(self, master)
            self.path = path
            self.pack()
            self.var = Tkinter.BooleanVar()
            self.createWidgets()

    #    TCP PORT, timeout, chunksize, broadcastintervall
    def createWidgets(self):
        #TCP Port
        self.l1 = Tkinter.Label(self, text="TCP-Port")
        self.l1.grid(row=0, column=0)
     
        self.e1 = Tkinter.Entry(self)
        self.e1.grid(row=0, column=1)
        self.e1.insert(0, self.TCP_PORT)
       
        # Chunksize
        self.l3 = Tkinter.Label(self, text="Chunk-Size")
        self.l3.grid(row=2, column=0)
     
        self.e3 = Tkinter.Entry(self)
        self.e3.grid(row=2, column=1)
        self.e3.insert(0, self.CHUNK_SIZE)

        # Broadcast-Intervall
        self.l4 = Tkinter.Label(self, text="Broadcast-Intervall(sec)")
        self.l4.grid(row=3, column=0)
     
        self.e4 = Tkinter.Entry(self)
        self.e4.grid(row=3, column=1)
        self.e4.insert(0, self.BROADCASTINTERVALL)
        

        self.l6 = Tkinter.Label(self, text="History")
        self.l6.grid(row=4, column=0)

        self.history = Tkinter.Checkbutton(self, text="An oder aus", variable=self.var)
        self.history.grid(row=4, column=1)

        self.buttonframe=Tkinter.Frame(self)
        self.buttonframe.grid(row=5, columnspan=2, column=0, sticky=Tkinter.W)
        
        self.bok = Tkinter.Button(self.buttonframe, text="Speichern", command=self.writeConfig)
        self.bok.grid(row=5, column=0)
        self.beende = Tkinter.Button(self.buttonframe,text="Beenden", command=self._root().destroy)
        self.beende.grid(row=5, column=1)
    

    def writeConfig(self):
        opts = {}
        
        if self.e1.get():
            opts['tcpport'] = self.e1.get()

        if self.e3.get():
            opts['chunksize'] = self.e3.get()
        
        if self.e4.get():
            opts['broadcastintervall'] = self.e4.get()

        if self.var.get() == 0:
            opts['history']=  False
        elif self.var.get() == True:
            opts['history']=  True


        createDefaultConfig(self.path,opts)
        sys.exit(0)
