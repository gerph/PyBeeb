'''
Created on 14 Oct 2011

@author: chris.whitworth
'''

class LoggingDispatcher(object):
    def A(self, value, location):
        print "Saving %s to A" % value

    def X(self, value, location):
        print "Saving %s to X" % value

    def Y(self, value, location):
        print "Saving %s to Y" % value

    def memory(self, value, location):
        print "Saving %s to $%s" % (value, hex(location))

    def PC(self, value, location):
        print "Saving %s to the PC" % value

    def SP(self, value, location):
        print "Saving %s to the SP" % value

    def PS(self, value, location):
        print "Saving %s to the PS" % value

    def NW(self, value, location):
        print "(no writeback)"