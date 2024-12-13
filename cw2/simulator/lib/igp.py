from routingAbstractions import AbstractRoutingDaemon
from packet import RoutingPacket, Payload
import networkx as nx

class IGP(AbstractRoutingDaemon):

    def __init__(self):
        self._id = None
        self._sentPerInterface = {}
        self._graph = nx.DiGraph()  # Graph to hold the network topology
        self._fwd_table = None  # Reference to the forwarding table
        self._lastUpdateTime = 0  # Timestamp of the last update
        self._edgeTimestamps = {}  # Store timestamps for edges
        self._pendingParameters = {}  # Store parameters if set before bindToRouter
        self._interfaceToNeighbor = {}  # Map interface to neighbor router

    def setParameters(self, parameters):
        """Sets router-local parameters such as link weights."""
        print("[IGP] Received parameters: {}".format(parameters))
        if self._id is None:
            # Store parameters for later use if router ID is not set
            self._pendingParameters = parameters
        else:
            self._applyParameters(parameters)

    def _applyParameters(self, parameters):
        """Applies the parameters to the graph."""
        for iface, weight in parameters.get('weights', {}).items():
            self._interfaceToNeighbor[iface] = None  # Initialize interface-to-neighbor mapping

    def bindToRouter(self, router_id, fwd_table):
        """Sets the router ID and binds the forwarding table."""
        self._id = router_id
        self._fwd_table = fwd_table
        print("[IGP] Bound to router {}. Current forwarding table:\n{}".format(
            router_id, fwd_table.getDescription(router_id)))
        # Apply any pending parameters now that the ID is available
        if self._pendingParameters:
            self._applyParameters(self._pendingParameters)
            self._pendingParameters = {}

    def update(self, interfaces2state, currentTime):
        """Updates the routing information at the beginning of each simulation round."""
        print(f"[IGP] Router {self._id} update at time {currentTime}.")
        self._lastUpdateTime = currentTime

        # Reset sentPerInterface for the new round
        self._sentPerInterface = {iface: False for iface in interfaces2state}

        for iface, state in interfaces2state.items():
            neighbor = self._getNeighborFromInterface(iface)
            if state == 'down' and neighbor:
                # Remove edge if the link is down
                if self._graph.has_edge(self._id, neighbor):
                    print(f"[IGP] Removing edge between {self._id} and {neighbor} due to interface {iface} down.")
                    self._graph.remove_edge(self._id, neighbor)
                    self._edgeTimestamps.pop((self._id, neighbor), None)
            elif state == 'up' and neighbor:
                # Add or update edge if the link is up
                print(f"[IGP] Adding/updating edge between {self._id} and {neighbor} due to interface {iface} up.")
                self._graph.add_edge(self._id, neighbor, weight=1)
                self._edgeTimestamps[(self._id, neighbor)] = currentTime

        # Recompute shortest paths to reflect the updated topology
        self._computeShortestPaths()

    def _getNeighborFromInterface(self, iface):
        """Determine the neighbor router connected to the given interface."""
        return self._interfaceToNeighbor.get(iface)

    def processRoutingPacket(self, packet, iface):
        """Processes incoming routing packets."""
        payload_data = packet.getPayload().getData()
        sender_router = payload_data[0].get('sender', None)
        print(f"[IGP] Router {self._id}: Received routing packet from {sender_router} on interface {iface}")

        # Establish the link between this router and the sender if not already established
        if sender_router and not self._graph.has_edge(self._id, sender_router):
            self._graph.add_edge(self._id, sender_router, weight=1)
            self._edgeTimestamps[(self._id, sender_router)] = self._lastUpdateTime
            self._interfaceToNeighbor[iface] = sender_router

        # Update the local graph with the received topology information
        for edge in payload_data[0].get('topology', []):
            source, target, attr = edge
            weight = attr.get('weight', 1)
            timestamp = attr.get('timestamp', 0)

            # Only update if the edge is newer than the current one
            if ((source, target) not in self._edgeTimestamps or
                    timestamp > self._edgeTimestamps[(source, target)]):
                self._graph.add_edge(source, target, weight=weight)
                self._edgeTimestamps[(source, target)] = timestamp

        # Recompute shortest paths
        self._computeShortestPaths()

    def generateRoutingPacket(self, iface):
        """Generates routing packets to share link-state information."""
        # Only send a packet if not already sent in this round
        if iface not in self._sentPerInterface or not self._sentPerInterface[iface]:
            self._sentPerInterface[iface] = True
            pkt = RoutingPacket(self._id)
            payload = Payload()
            payload.addEntry({
                'sender': self._id,  # Include the sender router ID
                'topology': [(u, v, {**self._graph[u][v], 'timestamp': self._edgeTimestamps[(u, v)]})
                             for u, v in self._graph.edges()],  # Share the topology with timestamps
            })
            pkt.setPayload(payload)
            print(f"[IGP] Router {self._id}: Sending routing packet from interface {iface}")
            return pkt
        else:
            print(f"[IGP] Router {self._id}: Already sent routing packet on interface {iface} in this round.")
            return None

    def _computeShortestPaths(self):
        """Computes shortest paths using Dijkstra's algorithm and updates the forwarding table."""
        if not self._graph:
            print(f"[IGP] Router {self._id}: No graph data available for path computation.")
            return

        # Initialize a set of all nodes in the graph
        all_nodes = set(self._graph.nodes)

        try:
            shortest_paths = nx.single_source_dijkstra_path(self._graph, self._id, weight='weight')
            reachable_nodes = set(shortest_paths.keys())

            # Update forwarding table for reachable nodes
            for dest, path in shortest_paths.items():
                if dest == self._id:
                    continue
                next_hop = path[1] if len(path) > 1 else None
                if next_hop:
                    # Handle ECMP by finding all equal-cost paths
                    all_next_hops = [iface for iface in self._interfaceToNeighbor if self._interfaceToNeighbor[iface] == next_hop]
                    self._fwd_table.setEntry(dest, all_next_hops)

            # Remove unreachable nodes from the forwarding table
            unreachable_nodes = all_nodes - reachable_nodes
            for node in unreachable_nodes:
                self._fwd_table.setEntry(node, [])

            print(f"[IGP] Router {self._id}: Updated forwarding table:\n{self._fwd_table.getDescription(self._id)}")
        except nx.NetworkXNoPath:
            print(f"[IGP] Router {self._id}: No path to destination. Clearing forwarding table.")
            for node in all_nodes:
                self._fwd_table.setEntry(node, [])






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

