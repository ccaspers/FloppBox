# -*- coding: utf-8 -*-
'''
Created on 31.05.2012

@author: christian
'''
import urllib, tempfile, floppboxIO, logging, socket

class Job(object):
    '''
    classdocs
    '''
    
    #JOB-States
    MODE_READ = 0
    MODE_WRITE = 1
     
    #Possible origins of connection
    SRC_SELF = 2
    SRC_OTHER = 3
    
    #List of available Commands
    CMD_REQUEST_LIST = "REQUEST LIST"
    CMD_REQUEST_FILE = "REQUEST FILE"
    CMD_LIST = "LIST"
    CMD_FILE = "FILE"
    CMD_DELETE_FILE = "DELETE FILE"
    CMD_TERMINATOR = "\n\n"
    CMD_COMMANDS = [CMD_REQUEST_LIST, CMD_REQUEST_FILE, CMD_LIST, CMD_FILE, CMD_DELETE_FILE]
    
    def __init__(self, connection, chunk_size, filelist, root, cmd=None, fileinfo=None):
        ''' Jobobjekt zur Verwaltung der Datenübertragung über ein Socket '''
        # Wichtige Objekte
        self.chunk_size = chunk_size
        self.logger = logging.getLogger(__name__)
        self.root = root
        self.jobRoutine = None
        self.connection = connection    
        self.filelist = filelist
        self.fileinfo = fileinfo
        self.cmd = cmd
        self.result = None
        self.src = None
        self.relpath = None if fileinfo is None else fileinfo.keys()[0]
        # Scheint eine Anfrage von aussen zu sein
        if self.cmd is None:
            self.src = Job.SRC_OTHER
            # Vorbereiten um Kommando einzulesen
            self.mode = Job.MODE_READ 
        # Vorbereiten auf Download und um Kommando zu senden
        else:
            if cmd not in Job.CMD_COMMANDS:
                raise Exception("Unbekanntes Kommando")
            else:
                self.mode = Job.MODE_WRITE
                self.src = Job.SRC_SELF
        # Vorbereiten um Job bei Aufruf von work() zu konfigurieren
        self.jobRoutine = self._parseCommand   
        self.logger.debug("Neuen Job initialisiert")     
        
          
    
    def _parseCommand(self):
        # Wir sollen wohl was schicken, erstmal aber Kommando laden
        if self.isInitiator():
            self._prepareDownload()         
        else:
            self._prepareUpload()
        self._switchMode()
        
        
    
    def _prepareUpload(self):
        ''' Bereitet den Job für einen Upload vor '''
        self.logger.debug("recv()")
        msg = self.connection.recv(self.chunk_size)
        self.logger.info("Bereite Upload vor - MSG: %s" % msg.strip())  
        # File dran ?    
        if self._count_char(msg," ") == 2:
            self.cmd , self.relpath = msg.strip().rsplit(" ",1)
            self.relpath = urllib.unquote_plus(self.relpath)
            self.logger.info("Bereite Upload vor - MSG: %s" % msg.strip()) 
        else:
            self.cmd = msg.strip()
        # Irgendwas stimmt mit dem Kommando nicht   
        if self.cmd not in Job.CMD_COMMANDS:
            self.connection.send("BAD REQUEST!")
            self.jobRoutine = self._boolYielder()
        #REQUEST FILE    
        elif self.cmd == Job.CMD_REQUEST_FILE:
            #TODO: hier prüfen ob Datei gelöscht werden muss
            #entweder _sendfile, oder DELETE FILE
            self.jobRoutine = self._sendfile()
        #REQUEST LIST    
        elif self.cmd == Job.CMD_REQUEST_LIST:
            self.jobRoutine = self._sendlist()
            
            
            
    def _prepareDownload(self):
        ''' Bereitet den job für einen Download vor '''
        if self.cmd in [Job.CMD_REQUEST_LIST, Job.CMD_REQUEST_FILE, Job.CMD_DELETE_FILE] and self.fileinfo:
            self.relpath = self.fileinfo.keys()[0]
            codedfname = urllib.quote_plus(self.relpath)
            
            
        if self.cmd == Job.CMD_REQUEST_FILE:             # Eine Datei soll geschickt werden  
            self.cmd = self.cmd+" "+codedfname # Dateipfad anhängen
            self.jobRoutine = self._recvfile()      # SENDEN
            
        else:                                       # Wir wollen eine  Liste haben
            self.cmd = Job.CMD_REQUEST_LIST
            self.jobRoutine = self._recvlist()
            
            
        self.cmd += Job.CMD_TERMINATOR # Terminator :)          # Kommando Terminieren
        self.logger.info("Bereite Download vor - cmd: %s" % self.cmd)  
        self.connection.send(self.cmd)       

        
        



    def _recvfile(self):
        self.logger.info("Empfange Datei: %s" % self.relpath)
        tmpFileHandle = tempfile.TemporaryFile()
        self.logger.debug("recv()")
        msg = self.connection.recv(self.chunk_size)
        
        while Job.CMD_TERMINATOR not in msg:
            yield True
            self.logger.debug("recv()")
            msg += self.connection.recv(self.chunk_size)

        cmd,msg = msg.split(Job.CMD_TERMINATOR,1)
        
        if cmd != Job.CMD_FILE:
            self.logger.critical("Messageheader fehlerhaft: %s" % cmd)
            raise Exception("_recvfile - Wrong Messageheader")
        tmpFileHandle.write(msg)
        
        while True:
            yield True
            self.logger.debug("recv()")
            msg = self.connection.recv(self.chunk_size)
            if msg != '':
                tmpFileHandle.write(msg)
            else:
                self.logger.debug("Datei %s speichern" % self.relpath)
                floppboxIO.writeFileToDisk(tmpFileHandle, self.root, self.relpath, self.fileinfo, self.filelist)
                return
    


    def _recvlist(self):
        self.result = ""
        self.logger.debug("recv()")
        msg = self.connection.recv(self.chunk_size)
                
        while Job.CMD_TERMINATOR not in msg:
            yield True
            self.logger.debug("recv()")
            msg += self.connection.recv(self.chunk_size)
            yield True
        cmd,msg = msg.split(Job.CMD_TERMINATOR,1)
        self.logger.debug("")
        
        if cmd != Job.CMD_LIST:
            self.logger.critical("Messageheader fehlerhaft: %s" % cmd)
            raise Exception("_recvlist - Wrong Messageheader")
        self.logger.debug("Empfange Dateiliste von %s:%s" % self.connection.getpeername())        
        if msg == '':
            msg = self.connection.recv(self.chunk_size)
        while msg != '':
            self.result += msg
            yield True
            self.logger.debug("recv()")
            msg = self.connection.recv(self.chunk_size)
            
        self.logger.debug("Empfangene Liste:\n %s" % self.result)
        self.result = floppboxIO.Filelist.parse(self.result)
        ip = self.connection.getpeername()[0]
        for key in self.result:
            self.result[key]['ip'] = ip
        self.logger.info("Dateiliste erhalten von %s:%s" % self.connection.getpeername())
        return
    
    
    
    def _sendfile(self):
        try:
            f = open(self.root+"/"+self.relpath,"r")
            self.logger.debug("Datei geöffnet :: %s/%s" % (self.root,self.relpath))
            self.connection.send(Job.CMD_FILE+Job.CMD_TERMINATOR)
            yield True
            data  = f.read(self.chunk_size)
            while data != '':   
                self.logger.debug("Sende %s Byte" % len(data))
                self.connection.send(data)      
                yield True
                data  = f.read(self.chunk_size)
                
            f.close()
            self.logger.info("Datei geschlossen :: %s/%s" % (self.root,self.relpath))
        except:
            return

            
            
    
    def _sendlist(self):
        self.connection.send(Job.CMD_LIST+Job.CMD_TERMINATOR)
        yield True
        liststr = str(self.filelist)
        mygen = self._separate(liststr,1024)
        for part in mygen:
            self.logger.debug("sende ")
            self.connection.send(part)
            yield True
            
    
    
    def work(self):
        if self.jobRoutine == self._parseCommand:
            self.jobRoutine()
            return True
        else:
            try:
                return self.jobRoutine.next()
            except socket.error,e:
                self.result = None
                self.logger.warning("Job abgebrochen :: %s" % e)
            except StopIteration,e:
                self.logger.info("Job beendet Pfad: %s" % self.relpath)
            self.jobRoutine = self._boolYielder()
            return False
        
    def getResult(self):
        return self.result
    
################## Hilfsfunktionen ab hier    
      
      
    def _separate(self,text, size):
        ''' Erzeugt Generator zum splitten der Strings zur Übertragung '''
        tlen = len(text)
        end = tlen/size + (0 if tlen%size == 0 else 1)
        strings = (text[i*size:(i*size)+size] for i in xrange(0, end))
        return strings    


    def _count_char(self,text,char):
        ''' Zählt die Vorkommen des zeichens oder substrings '''
        return len([i for i in text if i == char])    
    
    
    
    def hasResult(self):
        if self.result is not None:
            return True
        return False    
    
    def hasFilename(self):
        return self.relpath != None
    
    def getFilename(self):
        return self.relpath
        
    def isDownload(self):
        if self.mode == Job.MODE_READ:
            return True
        elif self.mode == Job.MODE_WRITE:
            return False
        else:
            raise Exception("isDownload - job.mode falsch initialisiert")
        

    
    def isInitiator(self):
        ''' Gibt Auskunft darüber, wer die Verbindung aufgebaut hat'''
        if self.src == Job.SRC_SELF:
            return True
        elif self.src == Job.SRC_OTHER:
            return False  
        else:
            raise Exception("isInitaor - job.src nicht initialisiert")     
        
         
    def _switchMode(self):
        ''' Wechselt zwischen Lese- und Schreibmodus'''
        if self.mode == Job.MODE_READ:
            self.mode = Job.MODE_WRITE
        elif self.mode == Job.MODE_WRITE:
            self.mode = Job.MODE_READ
        else:
            raise Exception("_switchMode - job.mode nicht initialisiert")

    def _boolYielder(self,x=False):
        while True:
            yield x
        
        
        