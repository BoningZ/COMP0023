import json
import networkx as nx

from router import Router
from link import Link
from event import Event
from checkers import ShortestPathChecker, OverheadChecker, TracerouteChecker
from routingAbstractions import AbstractRoutingDaemon
from igp import IGP

###########
# Factory #
###########

"""
    Factory for routing daemons that can currently be used within the simulator
"""
class RoutingDaemonsFactory:
    def __init__(self):
        self._availableDaemons = {"IGP": IGP()}

    def getRoutingDaemon(self, daemonId):
        daemon = self._availableDaemons[daemonId]
        assert issubclass(daemon.__class__, AbstractRoutingDaemon)
        return daemon

##########
# Parser #
##########

class ConfigParser:
    def __init__(self, filename, s):
        self._routers = []
        self._events = []
        self._links = []
        self._tracesources = []
        self._sim = s
        print(f"Reading file {filename}")
        try:
            with open(filename, 'rt') as f:
                configData = json.load(f)
                self.process(configData)
        except Exception as e:
            print(f"Couldn't read {filename}: {e}")
        self._sim.add_routers(self._routers)
        self._sim.add_links(self._links)
        self._sim.add_events(self._events)

    def process(self, configData):
        routingGraph = nx.DiGraph()
        iface_weights = {}
        destinations = []
        topochanges_times = []

        # Process routers
        if 'routers' in configData:
            for router in configData['routers']:
                r = Router(
                    rId=router['rId'],
                    numOfInterfaces=router['numOfInterfaces']
                )
                if 'updateInterval' in router and router['updateInterval'] > 1:
                    r.setUpdateInterval(router['updateInterval'])
                if 'verbose' in router:
                    r.setVerbose(router['verbose'] == 'True')
                proto = router['routingProtocol']
                ra = RoutingDaemonsFactory().getRoutingDaemon(proto)
                params = {}
                if 'routingProtocols' in configData and proto in configData['routingProtocols']:
                    if 'all-routers' in configData['routingProtocols'][proto]:
                        params.update(configData['routingProtocols'][proto]['all-routers'])
                    if router['rId'] in configData['routingProtocols'][proto]:
                        params.update(configData['routingProtocols'][proto][router['rId']])
                ra.setParameters(params)
                r.setRoutingDaemon(ra)
                self._routers.append(r)
                destinations.append(router['rId'])
                if 'weights' in params:
                    for linkid in params['weights']:
                        iface_weights[linkid] = params['weights'][linkid]

        # Process links
        if 'links' in configData:
            for link in configData['links']:
                r0, i0 = link['interfaces'][0].split('-')
                r1, i1 = link['interfaces'][1].split('-')
                conf_props = {}
                if 'properties' in link:
                    conf_props = link['properties']
                l = Link(
                    r0=r0,
                    i0=link['interfaces'][0],
                    r1=r1,
                    i1=link['interfaces'][1],
                    linkId=link['id'],
                    prop=conf_props,
                )
                if link['status'] == "up":
                    l.setState(True)
                elif link['status'] == "down":
                    l.setState(False)
                else:
                    print(f"Unknown link state {link['status']}")
                self._links.append(l)
                routingGraph.add_edge(r0, r1, linkid=link['id'], interface=link['interfaces'][0], weight=iface_weights[link['interfaces'][0]])
                routingGraph.add_edge(r1, r0, linkid=link['id'], interface=link['interfaces'][1], weight=iface_weights[link['interfaces'][1]])

        # Process events
        for event in configData['events']:
            if event['type'] == "send":
                args = [event['src'], event['dest']]
                if 'ttl' in event:
                    args += [event['ttl']]
                e = Event(event['type'], int(event['time']), args)
                self._events.append(e)

            elif event['type'] == "uplink" or event['type'] == "downlink":
                e = Event(event['type'], int(event['time']), event['link'])
                self._events.append(e)
                if int(event['time']) not in topochanges_times:
                    topochanges_times.append(int(event['time']))

            elif event['type'] == "stop":
                self._sim.set_stop_time(int(event['time']))

            elif event['type'] == "dumpfib":
                args = []
                args.append(event['args'])
                e = Event(event['type'], int(event['time']), args)
                self._events.append(e)

            elif event['type'] == "dumpTrafficStats":
                args = []
                args.append(event['args'])
                e = Event(event['type'], int(event['time']), args)
                self._events.append(e)

            elif event['type'] == "traceroute":
                args = [event['src'], event['dest']]
                e = Event(event['type'], int(event['time']), args)
                self._events.append(e)
                self._tracesources.append(event['src'])

            elif event['type'] == "stopOriginateIcmp":
                args = [event['router'], event['interface']]
                e = Event(event['type'], int(event['time']), args)
                self._events.append(e)

            else:
                print(f"Unrecognized event: {event}")
                exit(1)

        # Create checkers and set them to simulator
        tracerouters = [r for r in self._routers if r.getId() in self._tracesources]
        pathchecker = ShortestPathChecker(self._routers, self._links, routingGraph, destinations, reconverge_times=topochanges_times)
        simcheckers = [pathchecker, OverheadChecker(self._routers), TracerouteChecker(tracerouters,self._routers)]
        self._sim.set_checkers(simcheckers)

