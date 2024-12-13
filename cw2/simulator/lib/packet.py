import random
from enum import Enum

"""
    Class that specifies all used packet types.
"""
class PacketTypes(Enum):    
    UNKNOWN = "unknown"            # unknown packet, used before a packet is classified.
    DATA = "data"                  # data packet
    ROUTING = "routing"            # control-plane packet, supposed to be exchanged between routing daemons
    ICMP = "icmp"                  # error packet
    BROADCAST = "BCAST"            # packet sent in broadcast
    UNKNOWNADDR = "UNKNOWN_ADDR"   # unknown address

"""
    Class that represents the payload of a packet.
"""
class Payload:
    _data = None
    
    def __init__(self):
       self._data = list()
    
    def addEntry(self, o):
       self._data.append(o)

    def getData(self):
       return self._data

"""
    The Packet class models a network packet. 
"""
class Packet:
    _ttl = 255
    _seq = 0

    """
        The Packet constructor for the super class. This defaults to
        setting the packet type to be the UNKNOWN type. 
    """
    def __init__(self, s, d):
       self._src = s
       self._dst = d
       random.seed()
       self._srcport = 50000
       self._dstport = 8080
       self._type = PacketTypes.UNKNOWN.value
       self._data = Payload()
       self._seq = 0

    """
        Simple to string method.
    """
    def __str__(self):
        s = "type {} src {}:{} dst {}:{} ttl {} seq {}".format(self._type, self._src, self._srcport, self._dst, self._dstport, self._ttl, self._seq)
        if self._type == PacketTypes.DATA.value:
            if len(self._data.getData()) > 0:
                s += " path"
                d = self._data.getData()
                for i in d:
                    s += " ({})".format(i)
        return s

    ## Getters ##

    def getSource(self):
       return self._src

    def getDestination(self):
       return self._dst

    def getSourcePort(self):
       return self._srcport

    def getDestinationPort(self):
       return self._dstport

    def getType(self):
       return self._type;

    def getSequenceNumber(self):
       return self._seq

    def getPayload(self):
       return self._data

    def getTtl(self):
       return self._ttl

    ## Setters ##

    def setSourcePort(self, val):
       self._srcport = val

    def setDestinationPort(self, val):
       self._dstport = val

    def setSequenceNumber(self, s):
       self._seq = s

    def setType(self, t):
       self._type = t

    def setPayload(self, d):
       self._data = d

    def decrementTtl(self):
       self._ttl -= 1

    def setTtl(self,value):
       self._ttl = int(value)

"""
    This class represents a control-plane packet exchanged between routing daemons.
"""
class RoutingPacket(Packet):
  def __init__(self, src):
    self._src = src
    self._dst = PacketTypes.BROADCAST.value
    self._type = PacketTypes.ROUTING.value
    self._srcport = 2300
    self._dstport = 2300

