#-*- coding: utf-8 -*-
'''
Created on 30.06.2012

@author: ccasp001
'''
import unittest,os
from floppboxIO import Filelist

testfolder = os.getcwd()+"/testfolder"

class FloppboxTest(unittest.TestCase):
    

    def setUp(self):
        self.testlist = Filelist(testfolder)


    def tearDown(self):
        self.testlist= None


    def testFilelistInit(self):
        '''
        Testet die Initialisierung der Liste
        '''
        assert len(self.testlist.keys()) == 3
        
    def testFileListInitChanged(self):
        '''
        Prüft ob die Fileliste hasChanged auf False setzt
        und nach erneutem Prüfen aller Einträge weiterhin
        auf False steht wenn keine Änderungen anstanden
        '''
        assert self.testlist.hasChanged() is True
        assert self.testlist.hasChanged() is False
        self.testlist.checkall(testfolder)
        for key in self.testlist.keys():
            print {key : self.testlist[key]}
        assert self.testlist.hasChanged() is False

    def suite(self):
        suite = unittest.TestSuite()
        suite.addTest(FloppboxTest("filelist_init_test"))
        return suite

if __name__ == "__main__":
    #import sys;sys.argv = ['', 'Test.testName']
    unittest.main()