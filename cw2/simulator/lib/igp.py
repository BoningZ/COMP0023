from routingAbstractions import AbstractRoutingDaemon
from packet import RoutingPacket,Payload

class IGP(AbstractRoutingDaemon):

    ## Initializers ##

    "Constructor"
    def __init__(self):
        self._id = None
        self._sentPerInterface = {}

    "Setter of router-local parameters specified in the configuration and of options to be applied to all routers"
    def setParameters(self, parameters):
        print("[IGP] Received parameters: {}".format(parameters))

    "Setter of the router ID and reference to forwarding table used to forward packets"
    def bindToRouter(self, router_id, fwd_table):
        self._id = router_id
        print("[IGP] Current forwarding table of {}\n{}".format(router_id,fwd_table.getDescription(router_id)))

    ## Interactions with Router object ##

    "Refresher that is run at the beginning of every simulation round."
    def update(self, interfaces2state, currentTime):
        pass

    "Processor of a new packet received by the router and destined to this routing algorithm."
    def processRoutingPacket(self, packet, iface):
        print("[IGP] Router {}: I have just received a routing packet with payload {} on interface {}".format(self._id,packet.getPayload().getData(),iface))

    "Generator of control-plane packet to be sent out of the input interface in the current round. It must return a RoutingPacket object, or None (if no packet needs to be sent)."
    def generateRoutingPacket(self, iface):
        pkt = None
        if iface not in self._sentPerInterface:
            self._sentPerInterface[iface] = True
            pkt = RoutingPacket(self._id)
            payload = Payload()
            payload.addEntry("Hello world, here is router {} speaking".format(self._id))
            pkt.setPayload(payload)
        return pkt

     ## Traceroute implementation ##

    "Method called by Router, once per traceroute, to get all the packets to send out in order to implement the traceroute."
    def getTracerouteProbes(self, destination):
        return []

    "Method called by Router every time it receives an ICMP packet."
    def processPossibleTracerouteReply(self, icmpPacket):
        pass

    "Method that should return the output of the last completed traceroute."
    def getTracerouteOutput(self):
        return ""

    ## Debug methods ##

    def __str__(self):
        s = "IGP object {}".format(hash(self))
        return s

