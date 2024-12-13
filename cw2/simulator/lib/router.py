import hashlib
from link import Link
from packet import Packet,PacketTypes

"""
    This class models the forwarding table of a router,
    used by the router to forward packets.
"""
class ForwardingTable:
    LOOPBACK = "local"

    def __init__(self):
        self._table = {}
        self._numWrites = 0

    def setEntry(self,destination,outifaces):
        if not type(outifaces) is list:
            raise Exception("Incorrect format of FIB entry: outgoing interfaces {} are not a list".format(outifaces))
        self._table[destination] = outifaces
        self._numWrites += 1

    def removeEntry(self,destination):
        self._table.pop(destination,None)

    # Given that destinations are "router names", this method implements exact match, for simplicity.
    # Real routers instead need to support IP prefixes as destinations, and hence to rely on longest prefix match.
    def getNextHops(self,destination):
        if destination not in self._table:
            return []   
        return sorted(self._table[destination])

    def getTotalWrites(self):
        return self._numWrites

    def __str__(self):
        desc = ""
        alldests = list(self._table.keys())
        if len(alldests) == 0:
            return "<empty>\n"
        for d in sorted(alldests):
            if self._table[d] == ["local"]:
                desc += "{} directly connected\n".format(d)
            else:
                desc += "{} via {}\n".format(d,", ".join(self._table[d]))
        return desc

    def getDescription(self,routerid):
        return "FIB router {}\n{}".format(routerid,self)

"""
    This class implements the data-plane logic of the simulated router.
    It implements forwarding, but delegates the computation of forwarding
    entries to an input RoutingAlgorithm.
"""
class Router:
    _SENT = 0
    _RECV = 1
    _DROP = 2
    _FORW = 3
    
    """
        The Router constructor takes as input
        - rId: the router id
        - numOfInterfaces: number of physical network interfaces of the router
        - ra: the routing algorithm
    """
    def __init__(self, rId, numOfInterfaces):
        self._id = rId
        self._num_interfaces = numOfInterfaces
        self._links = {}
        self._fib = ForwardingTable()

        self._counter = [0,0,0,0,0]
        self._counter[self._SENT] = 0
        self._counter[self._RECV] = 0
        self._counter[self._DROP] = 0
        self._counter[self._FORW] = 0
        self._numRoutingPackets = 0         # sent control-plane packets
        self._originatedIcmpPackets = {}    # interface receiving expired packets -> number of received expired packets

        self._ralg = None
        self._current_time = 0
        self._update_interval = 1
        self._updates_buffer = []

        self._ifaces_noicmp = set([])
        self._last_traceout = None

        self._verbose = True
        print("Created router {}".format(self.getId()))


    ## Setter methods ##

    def addLink(self, l):
        i0 = l.getInterface(0)
        r0 = l.getRouter(0)
        i1 = l.getInterface(1)
        r1 = l.getRouter(1)
        print("Adding link {}".format(l))
        if (r0 == self._id):
            self._links[i0] = l
        elif (r1 == self._id):
            self._links[i1] = l

    def setTimeStep(self, time):
        self._current_time = int(time)

    def setUpdateInterval(self, value):
        self._update_interval = int(value)

    def setRoutingDaemon(self, ra):
        self._ralg = ra
        self._ralg.bindToRouter(self._id,self._fib)

    def setVerbose(self, boolean):
        self._verbose = boolean

    def stopOriginateICMPs(self, interface):
        print("Set ICMP filter on interface {} of router {}".format(interface,self.getId()))
        self._ifaces_noicmp.add(interface)


    ## Getter methods ##

    def getId(self):
       return self._id;

    def getLinks(self):
       return self._links

    def getForwardingTable(self):
       return self._fib

    def getCurrentTime(self):
        return int(self._current_time)

    def getNumberRoutingPackets(self):
        return self._numRoutingPackets

    def getNumInterfaces(self):
        return self._num_interfaces

    def isInterfaceUp(self, iface):
        # the loopback interface is always up
        if (iface == self._fib.LOOPBACK):
            return True
        else:
            return self._links[iface].isUp()

    def getStateAllInterfaces(self):
        linksState = {}             #  dictionary: interface -> "up"/"down"
        for i in self._links:
            if self.isInterfaceUp(i):
                linksState[i] = "up"
            else:
                linksState[i] = "down"
        return linksState

    def getTracerouteOutput(self):
        return self._ralg.getTracerouteOutput()

    def getSentTrafficPackets(self):
        return self._counter[self._SENT]

    def getReceivedTrafficPackets(self):
        return self._counter[self._RECV]

    def getNumExpiredPacketsPerInterface(self):
        return self._originatedIcmpPackets
        
    def __str__(self):
        s = "Router {} has {} interfaces".format(self._id,self._num_interfaces)
        if self._ralg:
            s += ", routing algorithm {}".format(self._ralg)
        return s


    ## Debugging methods ##
   
    def _printIfVerbose(self, string):
        if self._verbose:
            print(string)

    """
        Dump the forwarding table to stdout
    """
    def dumpForwardingTable(self):
        print("{}".format(self._fib.getDescription(self._id)))

    """
        Dump packet Stats to stdout for both the router and each link.
        s : sent , r : recv , d : drop , f : forw
    """
    def dumpTrafficStats(self,skipPerLink=False):  
        s = "Traffic stats for {} : ".format(self._id)
        s += " s {}".format(self._counter[self._SENT])
        s += " r {}".format(self._counter[self._RECV])
        s += " d {}".format(self._counter[self._DROP]) 
        s += " f {}".format(self._counter[self._FORW]) 
        s += "\n"

        if not skipPerLink:
            for lId in self._links:
                s += "{}\n".format(self._links[lId].dumpPacketStats());
        print(s, end="")

    """
        Implements traceroute towards a destination.
        Ideally, it should test all the ECMP paths, with a minimal
        number of probes.
    """
    def launchTraceroute(self,dest):
        print("Router {} launching traceroute towards {}".format(self._id,dest))
        for probe in self._ralg.getTracerouteProbes(dest):
            self.send(probe)


    ## Main simulation method ##

    """
        Sends a packet, either directly on an interface (if one is specified)
        or looks the interface up in the forwarding table.
        Handles cases of no interface, down interface and expired TTL.
    """
    def send(self, p, out_iface=None, in_iface=None, description=None):
        if p == None:
            return
        # by default, count and print information only for the originated data packets
        printInfo = (p.getType() == PacketTypes.DATA.value)
        if p.getSource() == self._id and printInfo:
            self._counter[self._SENT] += 1
        if description:
            print(description)
        # compute outgoing interface
        outgoing_iface = out_iface
        if outgoing_iface == None:
            ifaces = self._fib.getNextHops(p.getDestination())
            if (len(ifaces) == 0):
                if printInfo: self._printIfVerbose("Router {}: No outgoing interfaces, DROP packet {}".format(self._id,p))
                self._counter[self._DROP] += 1
                return
            outgoing_iface = self._getOutgoingIface(ifaces,p)
        # actually send packet, unless outgoing interface is down or packet is expired
        if not self.isInterfaceUp(outgoing_iface):
            if printInfo: self._printIfVerbose("Router {}: Outgoing interface {} is down, DROP packet {}".format(self._id,outgoing_iface,p));
            self._counter[self._DROP] += 1
        elif p.getTtl() < 1:
            if printInfo: self._printIfVerbose("Router {}: Expired TTL, DROP packet ".format(self._id,p))
            self._counter[self._DROP] += 1
            newp = self._generateIcmpPacket(p,in_iface)
            self.send(newp)
        else:
            p.decrementTtl()
            if printInfo:
                if len(p.getPayload().getData()) == 0:
                    self._printIfVerbose("Router {}: Sent NEW packet {} over outgoing interface {}".format(self._id,p,outgoing_iface))
                else:
                    self._printIfVerbose("Router {}: Forwarded packet {} over outgoing interface {}".format(self._id,p,outgoing_iface))
            if outgoing_iface == self._fib.LOOPBACK and p.getType() == PacketTypes.ICMP.value:
                pass
            else:
                self._links[outgoing_iface].enqueuePackets(self._id, p)
            if (p.getSource() != self._id):
                self._counter[self._FORW] += 1

    """
        Main interface method, called by simulator at each time step.
    """
    def go(self):
       self._ralg.update(self.getStateAllInterfaces(),self.getCurrentTime())
       self._processPackets()
       self._sendRoutingMessages()
       self._finalizeIteration()

    ## Support simulation methods (meant to be private) ##

    """
        Loop through all the interfaces checking to see if there is 
        a packet to receive and process it. If it is destined for us
        print a message. If it is a broadcast packet pass it to the 
        routing algorithm to decode, we only broadcast routing packets.
        Otherwise we forward the packet.
    """
    def _processPackets(self):
        # collect new packets if any
        for iface in self._links:
            while True:
                p = self._recv(iface)
                if p is None:
                    break
                if (p.getDestination() == self._id):
                    if p.getTtl() < 1:
                        self._printIfVerbose("Router {}: Expired TTL, DROP packet ".format(self._id,p))
                        self._counter[self._DROP] += 1
                        newp = self._generateIcmpPacket(p,iface)
                        self.send(newp)
                    else:
                        self._printIfVerbose("Router {}: Received packet {}".format(self._id,p))
                        self._counter[self._RECV] += 1
                        if p.getType() == PacketTypes.ICMP.value:
                            self._ralg.processPossibleTracerouteReply(p)
                elif (p.getDestination() == PacketTypes.BROADCAST.value):
                    self._updates_buffer.append((p, iface))
                else:
                    self.send(p, in_iface=iface)
        # process buffered packets if any
        if (self._current_time % self._update_interval) == 0:
            for (buffpkt, buffiface) in self._updates_buffer:
                self._ralg.processRoutingPacket(buffpkt, buffiface)
            self._updates_buffer = []

    """
        Receives a packet on the interface specified, if no packet is 
        available null is returned.
    """
    def _recv(self, iface):
        return self._links[iface].dequeuePackets(self._id)

    """
        Calls the routing algorithm to generate a routing
        table packet for each interface and sends it on that
        interface.
    """
    def _sendRoutingMessages(self):
        p = None
        for iface in self._links:
            p = self._ralg.generateRoutingPacket(iface)
            if p is not None:
                self.send(p, out_iface=iface)
                self._numRoutingPackets += 1

    """
        Selects the actual outgoing interface for the input packet among
        the input list of possible interfaces.
    """
    def _getOutgoingIface(self,ifaces,packet):
        string2hash = "{}{}{}{}{}".format(self._id,packet.getSourcePort(),packet.getDestinationPort(),packet.getSource(),packet.getDestination())
        h = hashlib.new('sha256')
        h.update(string2hash.encode())
        hashnum = int(h.hexdigest(),16) % len(ifaces)
        return ifaces[hashnum]

    """
        Generates an ICMP packet for the expired input packet.
    """   
    def _generateIcmpPacket(self, expired_packet, incoming_iface):
        self._incrementOriginatedIcmps(incoming_iface)
        if incoming_iface in self._ifaces_noicmp:
            return None
        newp = Packet(self.getId(),expired_packet.getSource())
        newp.setType(PacketTypes.ICMP.value)
        newp.setDestinationPort(expired_packet.getSourcePort())
        newp.setSequenceNumber(expired_packet.getSequenceNumber())
        return newp

    def _incrementOriginatedIcmps(self, expired_packet_iface):
        if expired_packet_iface not in self._originatedIcmpPackets:
            self._originatedIcmpPackets[expired_packet_iface] = 0
        self._originatedIcmpPackets[expired_packet_iface] += 1

    def _finalizeIteration(self):
        self._ralg.finalizeIteration()
        traceout = self.getTracerouteOutput()
        if traceout and self._last_traceout != traceout:
          self._last_traceout = traceout
          print(traceout)

