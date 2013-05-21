#-*-coding:utf-8-*-
'''
Created on 08.06.2012

@author: ccasp001
'''
from floppboxIO import Filelist
from job import Job
import floppboxIO
import logging
import os
import pickle
import socket

class JobManager(object):
    '''
    classdocs
    '''
    def __init__(self, rootfolder, group, chunk_size,history = False):
        '''
        Constructor
        '''
        self.histrory = history
        self.chunk_size = chunk_size
        self.logger = logging.getLogger(__name__)
        self.jobDict = {}
        self.path = rootfolder+"/"+group
        self.listfile = rootfolder + "/." + group + ".list"
        self.rList = []
        self.wList = []
        self.difflist = Filelist()
        
        self.mylist = self.loadFilelist()
        self.logger.debug("JobManager initialisiert mit Liste: %s" % self.mylist)
        
        
        
    def loadFilelist(self):
        if(os.path.isfile(self.listfile)):
            try:
                tempFilelist = pickle.load(open(self.listfile))
                tempFilelist.checkall(self.path)
                return tempFilelist
            except:
                os.remove(self.listfile)
        return Filelist(self.path)
    
    
    
    def saveFilelist(self):
        try:
            pickle.dump(self.mylist, open(self.listfile, "w+"), pickle.HIGHEST_PROTOCOL)
        except:
            self.logger.info("Fehler beim serialisieren der Filelist")
        
    def jobben(self, sock):
        actjob = self.jobDict.get(sock)
        
        if actjob.work() is False:
            
            if actjob.hasResult():
                templist = self.mylist.diff(actjob.getResult())
                for key in self.getJobFilenames():
                    templist.pop(key)
                self.difflist.update(self.difflist.diff(templist))
            
            self.jobDict.pop(sock)
            self.logger.debug("Socket aus JobManager entfernt")
            self.logger.debug("Socket geschlossen")
            sock.close()
            self.logger.info("Job abgeschlossen")
            self.logger.debug("Aktuell werden %s Jobs verwaltet" % len(self.jobDict))
            self.logger.debug("JobDict" + str(self.jobDict))
            
    def kill(self,sock):
        sock.close
        self.jobDict.pop(sock)
            
    
    def getJobFilenames(self):
        ret = []
        for job in self.jobDict.keys():
            if self.jobDict[job].isDownload() and self.jobDict[job].hasFilename():
                ret.append(self.jobDict[job].getFilename())
        return ret
    
               
    def getRList(self):
        "get Read List"
        return self.rList
    
    def getWList(self):
        "get Write List"
        return self.wList
    
    def getJob(self, sock):
        "get job"
        return self.jobDict[sock]
    
    def addDownloadJob(self, sock, cmd, fileDic=None):
        "add a download job"
        self.jobDict[sock] = Job(sock, self.chunk_size, self.mylist, root=self.path, cmd=cmd, fileinfo=fileDic)
        self.logger.debug("Download-Job hinzugefügt")


    def addUploadJob(self, sock):
        "add a upload job"
        self.jobDict[sock] = Job(sock, self.chunk_size, self.mylist, root=self.path)
        self.logger.debug("Upload-Job hinzugefügt")

        
    # False, wenn bereits ein job für die ip besteht, true sonst
    def prepareRequestListJobs(self,ip, port):
        # überprüfe ob für die Ip adresse schon ein job existiert, wenn ja -> kein neuen job anlegen
        for actSock in self.jobDict.keys():
            try:
                if actSock.getpeername()[0] == ip:
                    return False
            except socket.error ,e:
                self.kill(actSock)
    
        actSock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        try:
            actSock.connect((ip,port))
            self.addDownloadJob(actSock, "REQUEST LIST")
            return True
        except:
            return False
            
            
    
    def createDownload(self, filename, port):
        actSock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        ip = self.difflist[filename]["ip"]          
        try:
            actSock.connect((ip,port))
            self.addDownloadJob(actSock, "REQUEST FILE", Filelist({filename: self.difflist[filename]}))
        except:
            pass
            
            
            
    def sortJobs(self):
        self.rList = []
        self.wList = []
        self.logger.debug("Aktuel %s Jobs in Liste" % len(self.jobDict.keys()))
        for sock in self.jobDict.keys():
            # Ist der Job im Read-Mode oder im Write Mode
            if self.jobDict[sock].isDownload():
                # Read Mode
                self.rList.append(sock)
                self.logger.debug("Socket in rList einsortiert")

            else:
                # Write Mode
                self.wList.append(sock)
                self.logger.debug("Socket in wList einsortiert")

                    
    def closeAllSockets(self):
        for sock in self.jobDict.keys():
            self.jobDict.pop(sock)
            sock.shutdown(socket.SHUT_RDWR)
            sock.close()
        self.logger.debug("Alle Sockets geschlossen")


    def getFilelist(self):
        return self.mylist
    
    def hasChanged(self):
        self.mylist.checkall(self.path)
        return self.mylist.hasChanged()
    
    def prepareJobs(self,iplist,tcpport):
        while len(self.jobDict) < 5 and len(iplist) > 0:
            ip = iplist.pop(0)
            self.prepareRequestListJobs(ip[0], ip[1])

        # lege jobs an um dateien zu erhalten, falls schon eine diffliste besteht
        existingFolders,existingFiles = self.difflist.getExistingKeys()
        deletedFolder,deletedFiles = self.difflist.getDeletedKeys()
        
        #Lösche alle Löschdateien
        for relpath in deletedFiles:
            floppboxIO.deleteFile(self.path,relpath)
            self.difflist.pop(relpath)
        
        #Lösche alle gelöschten Ordner
        for relpath in sorted(deletedFolder):
            floppboxIO.deleteDir(self.path, relpath)
        
        # Erzeuge alle Fremdordner
        for relpath in existingFolders:
            floppboxIO.createDirs(self.path, relpath.split("/"))
            self.difflist.pop(relpath)
        
        # Jobs für existierende dateien Anzeigen
        while len(self.jobDict) < 5 and len(existingFiles) > 0 :
            relpath = existingFiles[0]
            if self.difflist[relpath]['type'] == "file":
                self.createDownload(relpath, tcpport)
            existingFiles.pop(0)
            self.difflist.pop(relpath)
        
        # sortiere jobs in jeweilige liste
        self.sortJobs()
    
    def hasTasks(self):
        if len(self.jobDict) > 0:
            return True
        elif len(self.difflist) > 0:
            return True
