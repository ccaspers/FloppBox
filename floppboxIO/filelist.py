# -*- coding: utf-8 -*-
'''
Created on 30.05.2012

@author: christian
'''
import floppboxIO,urllib,os,logging,time

class Filelist(dict):
    ''' Objekt zum Verwalten von Dateiinformationen, eigentlich ein dict ;) '''
    EXISTS = 'exists'
    DELETED = 'deleted'

    def __init__(self,param = None):
        ''' Filelist kann leer, mit Ordnerpfad oder mit anderer Filelist initialisiert werden '''
        dict.__init__(self)
        self.logger = logging.getLogger(__name__)
        if param is not None:
            if type(param) is str:
                self.update(self.hashfolder(param))
            else:
                self.update(param)
        self.changed = True
        
    def __getstate__(self):
        d = self.__dict__
        del d['logger']
        return d
    
    def __setstate__(self, d):
        self.__dict__.update(d) 
        self.logger = logging.getLogger(__name__)   
        
    def diff(self,other):
        ''' 
        Berechnet die Differenz zwischen beiden Dateien, und gibt eine Liste mit den Dateien zurück, die 
        man von der Gegenseite benötigt
        '''
        for key in other.keys():
            if self.has_key(key):
                my = self[key]
                others = other[key]
                
                # Beide gelöscht, dann egal
                if my['status'] == Filelist.DELETED and others['status'] == my['status']:
                    other.pop(key)
                    
                # Beide existieren dann prüfen wer gewinnt
                elif my['status'] == Filelist.EXISTS and others['status'] == my['status']:
                    if my['hash'] == others['hash']:
                        other.pop(key)
                        
                    elif float(my['last_changed']) > float(others['last_changed']):
                        other.pop(key)
                        
                # Status der Dateien unterscheidet sich dann gewinnt das Datum
                else:
                    if float(my['last_changed']) > float(others['last_changed']):
                        other.pop(key)
        return other
    
    def __str__(self):
        '''
        Überschreibt die Stringrepräsentation der Filelist sodass die Liste direkt übers
        Netzwerk versendet werden kann
        '''
        ret = ""
        for key in self.keys():
            sub = self[key]
            content = [key,sub['hash'],repr(sub['last_changed']).strip("'"),repr(sub['last_access']).strip("'"),sub['type'],sub['status']]
            ret += ' '.join(map(lambda t: urllib.quote_plus(t),content))+"\n"
        return ret
    
    def __getitem__(self,k):
        return dict.__getitem__(self,k)
    
    def keys(self):
        return dict.keys(self)
    
    def checkEntryOld(self,root,key):
        path = root+"/"+key
        # Key ist in dict  un
        try:
            if self.has_key(key) and not (os.path.isfile(path) or os.path.isdir(path)) and not self[key]['status'] == Filelist.DELETED:
                self[key]['last_changed'] = time.time()
                self[key]['status']  = Filelist.DELETED
                self.changed = True
            elif not self.has_key(key) or ((os.path.isfile(path) or os.path.isdir(path)) and os.path.getmtime(path) > float(self[key]['last_changed'])):
                if os.path.isfile(path):
                    self.update(self.hashfile(root,key))
                else:
                    self.update(self.hashfolder(root,key))
                #sicher gehen dass datei als exists markiert ist
                self[key]['status'] = Filelist.EXISTS
                self.changed = True
        except OSError, e:
            self.logger.warning("Datei verschwunden %s" % key)
            if self.has_key(key):
                self[key]['last_changed'] = time.time()
                self[key]['status']  = Filelist.DELETED
                self.changed = True
                
                
    def checkEntry(self,root,key):
        path = root+"/"+key
        # Datei in liste:
        if self.has_key(key):
            #noch vorhanden
            if os.path.isdir(path) or os.path.isfile(path):
                #Daten Prüfen
                if os.path.getmtime(path) > float(self[key]['last_changed']):
                    # Bei Abweichung neu hashen
                    self.rehash(root, key)
            else:
                if not self[key]['status'] == Filelist.DELETED:
                #als gelöscht markieren
                    self.markAsDeleted(key)
        # Sonst
        else:
            if os.path.isdir(path) or os.path.isfile(path):
                # hashen und eintragen
                self.rehash(root, key)


    def markAsDeleted(self,key):
        self[key]['last_changed'] = time.time()
        self[key]['status']       = Filelist.DELETED
        self.changed              = True
        
        
        
    def rehash(self,root,relpath):
        path = root+"/"+relpath
        if os.path.isfile(path):
            self.update(self.hashfile(root,relpath))
        else:
            self.update(self.hashfolder(root,relpath)) 
        self.changed = True   
        
    def checkall(self,root):
        files = self.getFilenames(root)
        newfiles = [t for t in files if not self.has_key(t)]
        for key in self.keys()+newfiles:
            try:
                self.checkEntry(root,key)
            except:
                pass
            
            
        
    def folderlist(self):
        folderlist = []
        for item in dict.keys(self):
            path = "/".join(item.split("/")[:-1])
            if path not in folderlist:
                folderlist.append(path)
        return folderlist
    
    
    
    def hasChanged(self):
        t = self.changed
        self.changed = False
        return t
    
    
    
    def getFilenames(self,root,relPath = ""):
        datalist = []
        for data in sorted(os.listdir(root+"/"+relPath)):
            dpath = relPath+"/"+data if relPath != "" else data
            if os.path.isdir(root+"/"+dpath):
                datalist.extend(self.getFilenames(root,dpath))
            else:
                datalist.append(dpath)
        return datalist

            
    def update(self,x):
        dict.update(self,x)
    
    def getDeleted(self):
        return self.deleted
        
    @staticmethod
    def parse(msg):
        '''
        Parsed eine als String codierte Fileliste und gibt ein neues Objekt zurück
        '''
        logger = logging.getLogger("filelist")
        ret    = Filelist()
        msg    = msg.strip()
        
        if msg != '':
            for item in msg.split('\n'):
                parts = map(lambda t: urllib.unquote_plus(t),item.split(' '))
                if len(parts) == 6:
                    ret.update({parts[0]:
                         {
                          'hash'        :parts[1], 
                          'last_changed':float(parts[2]),
                          'last_access' :float(parts[3]),
                          'type'        :parts[4],
                          'status'      :parts[5]
                         }
                    })
                else:
                    logger.critical("Fileliste scheinbar unvollständig")
        return ret  
    
    def hashfolder(self,root,relPath = ""):
        datalist   = sorted(os.listdir(root+"/"+relPath if relPath != "" else root))
        hashlist   = {}
        folderhash = ''
          
        for data in datalist:
            if not data.startswith('.'):
                
                datapath = (relPath+"/"+data) if relPath != "" else data
                self.logger.debug("Root: %s :: Datapath : %s" % (root,datapath))
                
                if os.path.isdir(root+"/"+datapath):
                    hashinfo = self.hashfolder(root,datapath)
                    
                else:
                    hashinfo    = self.hashfile(root,datapath)
                    folderhash += hashinfo.get(datapath).get('hash')
                    
                hashlist.update(hashinfo)
        self.logger.debug("Ordner eingelesen - %s%s" % (root,relPath))  
        
        if relPath != "": 
            folderinfo = {}
            folderinfo['last_changed'] = os.path.getmtime(root+"/"+relPath)
            folderinfo['last_access']  = os.path.getatime(root+"/"+relPath)
            folderinfo['type']         = 'folder'
            folderinfo['hash']         = floppboxIO.hashstring(folderhash)
            folderinfo['status']       = Filelist.EXISTS            
            hashlist[relPath]          = folderinfo
            
        return hashlist



    def hashfile(self,root,datapath):
        abspath  = root+"/"+datapath
        filedict = {}
        fileinfo = {}
        f        = open(abspath)
        
        fileinfo['last_changed'] = os.path.getmtime(abspath)
        fileinfo['last_access']  = os.path.getatime(abspath)
        fileinfo['type']         = 'file'    
        fileinfo['status']       = Filelist.EXISTS
        fileinfo['hash']         = floppboxIO.hashfile(f) 
        
        f.close()
        filedict[datapath] = fileinfo    
        return filedict
    
    
    
    def getDeletedKeys(self):
        return self._getKeysByStatus(Filelist.DELETED)
    
    
    
    def getExistingKeys(self):
        return self._getKeysByStatus(Filelist.EXISTS)
    
    
    
    def _getKeysByStatus(self,status):
        folders = []
        files = []
        for key in self.keys():
            if self[key]['status'] == status:
                if(self[key]['type'] == 'folder'):
                    folders.append(key)
                else:
                    files.append(key)
        return (folders,files)
    
    
                
        
