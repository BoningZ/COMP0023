from abc import ABC, abstractmethod

"""
    Class documenting the methods that must be implemented by routing daemons.
"""
class AbstractRoutingDaemon(ABC):

    ## Initializers ##

    "Constructor"
    def __init__(self):
        pass
    
    "Setter of router-local parameters specified in the configuration and of options to be applied to all routers"
    @abstractmethod
    def setParameters(self, parameters):
        pass

    "Setter of the router ID and reference to forwarding table used to forward packets"
    @abstractmethod
    def bindToRouter(self, router_id, fwd_table):
        pass

    ## Interactions with Router object ##

    "Method called at the beginning of every simulation round."
    @abstractmethod
    def update(self, interfaces2state, currentTime):
        pass

    "Processor of a new packet received by the router and destined to this routing algorithm."
    @abstractmethod
    def processRoutingPacket(self, packet, iface):
        pass

    "Generator of control-plane packet to be sent out of the input interface in the current round. It must return a RoutingPacket object, or None (if no packet needs to be sent)."
    @abstractmethod
    def generateRoutingPacket(self, iface):
        pass

    "Method called at the end of every simulation round."
    def finalizeIteration(self):
        pass

    ## Traceroute implementation ##

    "Method called by Router, once per traceroute, to get all the packets to send out in order to implement the traceroute."
    @abstractmethod
    def getTracerouteProbes(self, destination):
        pass

    "Method called by Router every time it receives an ICMP packet."
    @abstractmethod
    def processPossibleTracerouteReply(self, icmpPacket):
        pass

    "Method that should return the output of the last completed traceroute."
    @abstractmethod
    def getTracerouteOutput(self):
        pass

