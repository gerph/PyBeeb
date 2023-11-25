'''
Created on 12 Oct 2011

@author: chris.whitworth
'''
from struct import unpack

class InvalidAddressException(Exception):
    def __init__(self, address):
        self.address = address

    def __repr__(self):
        return "Invalid address: %s" % hex(self.address)

class ValueOutOfRange(Exception):
    def __init__(self, value):
        self.value = value

    def __repr__(self):
        return "Value out of range: %s" % hex(self.value)

class Memory(object):
    class Map(object):
        def __init__(self, range, callback):
            self.range = range
            self.callback = callback

        def __repr__(self):
            return "<{}(base=&{:04x}, end=&{:04x}, callback={!r})>".format(self.__class__.__name__,
                                                                           self.base(), self.end(),
                                                                           self.callback)

        def base(self):
            return self.range[0]

        def end(self):
            # Note: end is inclusive
            return self.range[1]

        def isInMap(self, address):
            return True if address >= self.base() and address <= self.end()  else False

    MEMORYSIZE = 64 * 1024
    def __init__(self):
        self.memory = bytearray(self.MEMORYSIZE)
        self.protection = bytearray(self.MEMORYSIZE)
        self.maps = []

    def map(self, range, callback):
        self.maps.append( self.Map(range, callback) )

    def unmap(self, range):
        raise BaseException("Cannae do this")

    def getMapFor(self, address):
        maps = [ map for map in self.maps if map.isInMap(address) ]
        if len(maps) != 0:
            return maps[-1]
        else:
            return None

    def getNextMap(self, address):
        """
        Find the map that is next, after the address we requested.

        @param address: Address to search for

        @return: next map after the one requested, or None if no other maps present
        """
        next_map = None
        for map in self.maps:
            if map.base() > address:
                if not next_map or map.base() < next_map.base():
                    next_map = map
        return next_map

    def readByte(self, address):
        # TODO - add memory mapping
        if address < 0 or address > 0xffff:
            raise InvalidAddressException(address)

        map = self.getMapFor(address)

        if map != None:
            base = map.base()
            mappedDevice = map.callback
            readByte = mappedDevice.readByte(address - base)
        else:
            readByte = self.memory[address]

        #print "Read byte %s from %s" % (hex(readByte) , hex(address))
        return readByte

    def writeByte(self, address, value):
        # TODO - add memory mapping
        if address < 0 or address > 0xffff:
            raise InvalidAddressException(address)

        if value < 0 or value > 0xff:
            raise ValueOutOfRange(value)

        map = self.getMapFor(address)
        if map != None:
            base = map.base()
            mappedDevice = map.callback
            mappedDevice.writeByte(address - base, value)
        else:
            self.memory[address] = value

    def readBytes(self, address, size):
        """
        Read multiple bytes into a bytearray / mapped region.
        """
        if address < 0:
            raise InvalidAddressException(address)
        if address + size > 0xffff:
            raise InvalidAddressException(address + size)

        data = bytearray()

        while size:
            map = self.getMapFor(address)
            if map:
                end = address + size
                if end > map.end():
                    end = map.end()
                mappedDevice = map.callback
                base = map.base()
                map_data = bytearray([mappedDevice.readByte(offset) for offset in range(address - base, end - base)])
                data += map_data

            else:
                # No mapping region, so this is a regular byte array,
                # and we need to find out how far it extends.
                map = self.getNextMap(address)
                if map:
                    # there is a following map.
                    next_start = map.base()
                else:
                    next_start = 0x10000

                end = address + size
                if end > next_start:
                    end = next_start

                data += self.memory[address:end]

            size -= (end - address)
            address = end

        return data

    def writeBytes(self, address, value):
        """
        Read multiple bytes into a bytearray / mapped region.
        """
        size = len(value)
        if not isinstance(value, bytearray):
            value = bytearray(value)

        if address < 0:
            raise InvalidAddressException(address)
        if address + size > 0xffff:
            raise InvalidAddressException(address + size)

        while size:
            map = self.getMapFor(address)
            if map:
                end = address + size
                if end > map.end():
                    end = map.end()
                mappedDevice = map.callback
                base = map.base()
                for index in range(end - address):
                    mappedDevice.writeByte(address + index - base, value[index])
            else:
                # No mapping region, so this is a regular byte array,
                # and we need to find out how far it extends.
                map = self.getNextMap(address)
                if map:
                    # there is a following map.
                    next_start = map.base()
                else:
                    next_start = 0x10000

                end = address + size
                if end > next_start:
                    end = next_start

                self.memory[address:end] = value[:end - address]

            value = value[end - address:]
            size -= (end - address)
            address = end

    def readSignedByte(self, address):
        b = self.readByte(address)
        return unpack("b", chr(b))[0]

    def readWord(self, address):
        return self.readByte(address) + (self.readByte(address + 1) << 8)
