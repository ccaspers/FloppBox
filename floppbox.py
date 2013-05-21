#!/usr/bin/python
#-*-coding:utf-8-*-

import socket, select, sys, signal, os, uuid, time, math, logging, ConfigParser, gui, job, floppboxIO
from job import JobManager
 
class FloppBox:
    
    def __init__(self,group,groupfolder,configfolder,history = False):
        self.cfg        = self.loadConfig(configfolder,group)    
        self.rootfolder = os.getcwd()
        self.logger     = logging.getLogger(__name__)   
               
        # Variablen
        self.iplist = []
        self.myUUID = str(uuid.uuid1())
        
        # Netzwerkkonfig
        self.HOST           = ""
        self.UDP_PORT       = 5555
        
        self.TCP_PORT       = self.cfg["Network"]["tcpport"]
        self.TIMEOUT        = self.cfg["Network"]["timeout"]
        self.CHUNK_SIZE     = self.cfg["Network"]["chunksize"]
        job.Job.CHUNK_SIZE  = self.CHUNK_SIZE
        
        #Broadcast Setting
        self.lastCast           = 0
        self.BCAST_INTERVALL    = self.cfg["Network"]["broadcastintervall"]
        self.castIntro          = "HELLO %s" % group
        self.castText           = "%s %s %s" % (self.castIntro, self.TCP_PORT, self.myUUID)
        
        # Init
        self.jManager       = JobManager(self.rootfolder, group, self.CHUNK_SIZE,self.cfg['Misc']['history'])
        self.server         = self.getServer(self.HOST, self.TCP_PORT)   
        self.broadcaster    = self.getBroadcaster(self.HOST, self.UDP_PORT)
        self.broadcaster.sendto(self.castText, ("<broadcast>", self.UDP_PORT))
        
        self.logger.info("Floppbox initialisiert")
        
        
    def loadConfig(self,folder,group):   
        configfile = folder+"/."+group+".cfg"
        config = ConfigParser.ConfigParser()      
        if not os.path.isfile(configfile):
            createDefaultConfig(configfile,{})
        config.read(configfile)
        return self.config2Dict(config)
    
                            
    def config2Dict(self,config):
        ret = {}
        for section in config.sections():
            temp = {}
            for option in config.options(section):          
                try:
                    if section == 'Network':
                        temp[option] = config.getint(section, option)
                    elif section == 'Misc' and option == 'history':
                        temp[option] = config.getboolean(section, option)
                    else:
                        temp[option] = config.get(section,option)
                except:
                    self.logger.critical("exception on %s!" % option)
                    temp[option] = None
            ret[section] = temp
        return ret
        
    def getServer(self,HOST, port):
        server = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        server.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        server.bind((HOST,port))
        server.listen(1)
        self.logger.debug("TCP-Server gestartet")
        return server
    
    def getBroadcaster(self,HOST, port):
        broadcaster = socket.socket(socket.AF_INET, socket.SOCK_DGRAM, socket.IPPROTO_UDP)
        broadcaster.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR,1)
        broadcaster.setsockopt(socket.SOL_SOCKET, socket.SO_BROADCAST,1)
        broadcaster.setblocking(0)
        broadcaster.settimeout(float(self.BCAST_INTERVALL)/10.0)
        broadcaster.bind((HOST,port))
        self.logger.debug("UDP-Server gestartet")
        return broadcaster
    
    def stopTimeouts(self):
        if self.broadcaster and self.broadcaster.gettimeout() > float(self.BCAST_INTERVALL)/10.0:
            self.broadcaster.settimeout(float(self.BCAST_INTERVALL)/10.0)
    
    def closeAll(self):
        if self.jManager.histrory:
            self.jManager.closeAllSockets()
            self.jManager.saveFilelist()
        if self.server:
            self.server.shutdown(socket.SHUT_RDWR)
            self.server.close()
        if self.broadcaster:
            self.broadcaster.close()
        self.logger.debug("FLOPPBOX beendet")
        print "****FLOPPBOX**** bye"
        # sonst interrupted system call in sock.accept
        
    def findOthers(self):
        try:
            data = self.broadcaster.recvfrom(self.CHUNK_SIZE)
            
            if data[0].startswith(self.castIntro) and data[0] != self.castText:
                port = data[0].split(" ")[2]
                self.logger.info("Peer (%s,%s) gefunden"%data[1])
                peerIP = (data[1][0],int(port))
                if peerIP and peerIP not in self.iplist:
                    self.iplist.append(peerIP)
                    self.logger.debug("%s Peer in IP-Liste"%len(self.iplist))
        except socket.error:
            self.logger.debug("Keine Peers gefunden")
    
        
    def waitForBroadcasts(self):
        self.broadcaster.settimeout(self.BCAST_INTERVALL)
        self.logger.debug("Warte auf Peers, Blocking, %s Sekunden Timeout" % self.BCAST_INTERVALL)
        try:
            self.findOthers()
        except:
            self.broadcaster.setblocking(False)
            self.broadcaster.settimeout(0.1)
    
    def main(self):
        try: 
            self.jManager.prepareJobs(self.iplist,self.TCP_PORT)
            
            readSockets = self.jManager.getRList()+[self.server]
            writeSockets = self.jManager.getWList()+[(self.broadcaster)]
            self.broadcaster.setblocking(False)
            r, w, oob = select.select(readSockets,writeSockets ,[])
            for sock in r+w:
                try:                
                    if sock == self.broadcaster:
                        
                        self.findOthers()

                        if math.fabs(self.lastCast - time.time()) > self.BCAST_INTERVALL or self.jManager.hasChanged():
                            self.lastCast = time.time()
                            self.broadcaster.sendto(self.castText, ("<broadcast>", self.UDP_PORT))
                            self.logger.info("Sende Broadcast")
                            
                    elif sock is self.server: 
                        peer, addr = self.server.accept()
                        self.jManager.addUploadJob(peer)
                        self.logger.debug("Von Adresse %s:%s wurde Verbindung aufgebaut" % addr)
                    else:
                        self.jManager.jobben(sock)
                        
                except socket.error, e:
                    if sock == self.server:
                        self.logger.critical("Server-Socket Exception: %s" % e)
                    elif sock == self.broadcaster:
                        self.logger.info("Broadcast nicht gesendet o_O" % e)
                    elif self.jManager.jobDict.has_key(sock):
                        self.logger.warning("Job-Socket Exception %s" % e)
                        self.jManager.kill(sock)

#            if len(self.iplist) == 0 and not self.jManager.hasTasks():
#                self.logger.debug("Warte auf Peers")
#                self.waitForBroadcasts()
        except select.error, e:
            self.logger.critical("select.error: %s" % str(e)) 
            

def usage():
    print '''
################################################################
  FloppBox FileSynchronization Tool
################################################################
 
  Floppbox.py <Groupname> [-config] [-f] [-debug]
 
  Parameter
      -config : Öffnet ein grafisches Tool zur 
                zur Konfiguration der FloppBox
    
      -f      : Erstellt einen Ordner mit dem gewählten
                Gruppennamen, falls dieser nicht exisitiert  
    
      -debug  : Detailliertes Logfile mit Debuginformationen
          
                 
  Weitere Hinweise:
      Es ist darauf zu achten, dass ein Ordner mit 
      dem gewählten Gruppennamen existiert
     
################################################################    
  Autoren: Christian Caspers, Steven Dostert, Tobias Lehwalder
################################################################
'''

def createDefaultConfig(path,opts):
    config = ConfigParser.ConfigParser()    
    config.add_section('Network')
    config.set('Network', 'tcpport', '1111' if not opts.has_key('tcpport') else opts['tcpport'])
    config.set('Network', 'timeout', '10' if not opts.has_key('timeout') else opts['timeout'])
    config.set('Network', 'chunksize', '8192' if not opts.has_key('chunksize') else opts['chunksize'])
    config.set('Network', 'broadcastintervall','10' if not opts.has_key('broadcastintervall') else opts['broadcastintervall'])
    config.add_section('Misc')
    config.set('Misc', 'history', False if not opts.has_key('history') else opts['history'])
    
    with open(path, 'wb') as configfile:
        config.write(configfile)
    
def exithandler(signum,frame):
    global running
    if myBox:
        myBox.stopTimeouts()
    running = False
    
    
if __name__ == "__main__":
    myBox = None
    running = True
    signal.signal(signal.SIGINT, exithandler)
    loglevel = logging.INFO
    
    if(len(sys.argv[1]) < 2):
        usage()
        
    group = sys.argv[1]
    
    configfolder =  os.getcwd()
    groupfolder = os.getcwd()+"/"+group
    
    params = sys.argv[2:]
    
    if not os.path.isdir(groupfolder):
        if "-f" not in params:
            usage()
            sys.exit(1)
        else:
            os.mkdir(groupfolder)
            
    if "-debug" in params:
        loglevel = logging.DEBUG
        
    if "-config" in params:
        app = gui.configGUI.ConfigGUI(configfolder+"/."+group+".cfg")
        app.mainloop()
        
    if "-clear" in params:
        if os.path.isfile(configfolder+"/."+group+".cfg"):
            os.remove(configfolder+"/."+group+".cfg")
        if os.path.isfile(configfolder+"/."+group+".list"):
            os.remove(configfolder+"/."+group+".list")
        if os.path.isfile(configfolder+"/"+group+".log"):
            os.remove(configfolder+"/"+group+".log")
        
    
    logfile = configfolder+"/"+group+".log"
    logging.basicConfig(filename=logfile ,
                filemode='a+',
                format='%(asctime)s - %(name)s - %(funcName)s :: %(levelname)s - %(message)s',
                level=loglevel)
    logger = logging.getLogger(__name__)
    floppboxIO.initLogger()
        
    myBox = FloppBox(group,groupfolder,configfolder)    
    
    while running:
            myBox.main()
    myBox.closeAll()

