# -*- coding: utf-8 -*-
'''
Created on 31.05.2012

@author: christian
'''
import hashlib,os,logging
logger = None

def initLogger():
    global logger
    logger = logging.getLogger("floppboxIO")

def hashfile(f):
    m = hashlib.sha256()
    # größere Blöcke lesen damit lesen schneller abläuft
    blocksize = m.block_size**2
    data      = f.read(blocksize)
    
    while data:         
        m.update(data)
        data  = f.read(blocksize)
            
    return m.hexdigest()



def hashstring(string):    
    m     = hashlib.sha256(string)
    hashy = m.hexdigest()
    return hashy


def writeFileToDisk(src,root,relpath,info,filelist):
    src.seek(0)
    temphash = hashfile(src)
    if (info[relpath]["hash"] == temphash):
        src.seek(0)
        logger.info("Prüfe Verzeichnisse: %s/%s" % (root,relpath))
        createDirs(root,relpath.split("/")[:-1])
        
        try:
            saveFile(src,root,relpath,info)
            logger.debug("Dateipfad ist %s/%s" % (root, relpath))
                
            logger.info("Datei wird geprüft %s/%s" % (root, relpath))
            filelist.checkEntry(root, relpath)
            logger.info("Übertragung beendet: %s/%s" % (root,relpath))
            
        except:
            logger.critical("File nicht geschrieben: %s/%s" % (root,relpath))
    else:
        logger.warning("Datei Fehlerhaft übertragen %s/%s" % (root,relpath) )



def saveFile(temp,root,relpath,fileinfo):
    try:
        permanent = open(root+"/"+relpath, "w+")
        permanent.write(temp.read())
        permanent.close()
        atime = float(fileinfo[relpath]['last_access'])
        mtime = float(fileinfo[relpath]['last_changed'])
        os.utime(root+"/"+relpath, (atime, mtime))
    except:
        logger.error("Kann Datei nicht speichern: %s/%s" % (root,relpath))
        raise Exception("Kann Datei nicht speichern")
        
        
    
def createDirs(root,elements):
    os.chdir(root)
    if len(elements) > 0:
        for ele in elements:
            logger.debug("Erzeuge Verzeichnis %s%s" % (os.getcwd(),ele))
            if(not os.path.isdir(ele)):
                os.mkdir(ele)
            os.chdir(ele)
        os.chdir(root)
        
def deleteFile(root,relpath):
    path = root+"/"+relpath
    if(os.path.isfile(path)):
        os.remove(path)

def deleteDir(root,relpath):
    path = root+"/"+relpath
    if os.path.isdir(path) and os.listdir(path) == []:
        os.rmdir(path)
        