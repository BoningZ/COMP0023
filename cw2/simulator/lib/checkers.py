import networkx as nx
from abc import ABC, abstractmethod


class SimulationChecker(ABC):
    verbose = False

    def setVerbose(self, value):
        self.verbose = value

    @abstractmethod
    def check(self, time):
        pass

    @abstractmethod
    def printReport(self):
        pass


class ShortestPathChecker(SimulationChecker):
    def __init__(self, routers_list, links_list, routingGraph, destinations, reconverge_times=[]):
        self.routers = {}
        for r in routers_list:
            self.routers[r.getId()] = r
        self.links = links_list
        self.graph = routingGraph
        self.dests = destinations
        self.reconvergences = reconverge_times
        self.time2checks = {}

    def check(self, time):
        # update graph with currently available links
        currentGraph = self.graph.copy()
        for u,v,lid in self.graph.edges(data="linkid"):
            link_obj = [l for l in self.links if l.getId() == lid][0]
            if not link_obj.isUp():
                currentGraph.remove_edge(u,v)
        # check that all FIBs are consistent with the shortest paths
        compliant_fibs = True
        for d in self.dests:
            for r in currentGraph.nodes():
                if r != d:
                    expected_ifaces = []
                    try:
                        shortestpaths = list(nx.all_shortest_paths(currentGraph,r,d,weight='weight'))
                        expected_nhs = [path[1] for path in shortestpaths]
                        expected_ifaces = [currentGraph[r][nh]['interface'] for nh in expected_nhs]
                    except nx.exception.NetworkXNoPath:
                        pass
                    curr_ifaces = self.routers[r].getForwardingTable().getNextHops(d)
                    if set(curr_ifaces) != set(expected_ifaces):
                        if self.verbose:
                            print("FIB CHECK: Inconsistent FIB at {} for dest {}: expected {}; got {}".format(r,d,expected_ifaces,curr_ifaces))
                        compliant_fibs = False
        self.time2checks[time] = compliant_fibs

    def printReport(self):
        inconsistent_times = [t for t in self.time2checks if not self.time2checks[t]]
        print("Inconsistent forwarding exact time steps: {}".format(inconsistent_times))
        print("Inconsistent forwarding duration in time units: {}".format(len(inconsistent_times)))
        for t in self.reconvergences:
            reconvergence_duration = "0"
            if t in inconsistent_times:
                end_reconvergence = t+1
                while end_reconvergence in inconsistent_times and end_reconvergence not in self.reconvergences:
                    end_reconvergence += 1
                reconvergence_duration = end_reconvergence - t
            print("Inconsistent forwarding duration after topology change at time {}: {}".format(t,reconvergence_duration))


class OverheadChecker(SimulationChecker):
    def __init__(self, routers_list):
        self.routers = routers_list

    def check(self, time):
        pass

    def printReport(self):
        totalFibWrites = 0
        totalRoutingPackets = 0
        for r in self.routers:
            totalFibWrites += r.getForwardingTable().getTotalWrites()
            totalRoutingPackets += r.getNumberRoutingPackets()
        print("Number of FIB writes across all routers: {}".format(totalFibWrites))
        print("Number of control-plane packets: {}".format(totalRoutingPackets))


class TracerouteChecker(SimulationChecker):
    def __init__(self, tracesources_list, routers_list):
        self.tracesources = tracesources_list
        self.allrouters = routers_list
        self.traceresults = []

    def check(self, time):
        for router in self.tracesources:
            traceout = router.getTracerouteOutput()
            if traceout and traceout not in self.traceresults:
                self.traceresults.append(traceout)

    def printReport(self):
        if len(self.tracesources) == 0:
            return
        # print output of launched traceroutes
        traceresults_desc = "\n".join(self.traceresults)
        if len(traceresults_desc) > 0:
            print("{}\n".format(traceresults_desc))
        # print packets originated by traceroute sources
        for r in self.tracesources:
            print("Packets sent by {} (excluding control-plane ones): {}".format(r.getId(),r.getSentTrafficPackets()))
        # print expired packets received by all routers
        for r in self.allrouters:
            expired_received = r.getNumExpiredPacketsPerInterface()
            if len(expired_received) > 0:
                tot_received_expired = 0
                probed_ifaces = set([])
                for iface in expired_received:
                    tot_received_expired += expired_received[iface]
                    probed_ifaces.add(iface)
                print("Total number of expired packets received by {}: {}".format(r.getId(),tot_received_expired))
                print("Interfaces of {} that received an expired packet: {}".format(r.getId(),probed_ifaces))

