import os, sys, argparse
dirpath = os.path.dirname(os.path.realpath(__file__))
sys.path.insert(0, os.path.join(dirpath,'lib'))

from config import ConfigParser
from packet import Packet, PacketTypes

"""  
    The Simulator class loads the configuration and runs each
    router with the correct class for that router as specified in the 
    configurtion file. At each time step the Simulator carries out (in order)
    event processing process_events, routers tasks, process_routers, 
    packet forwarding process_packets
"""
class Simulator:
    _config_file = None
    _stop_time = 20
    _routers = []
    _events = []
    _links = []
    _packet_counter = 0
    _checkers = []

    """
        Simulator constructor, loads the configuration given
        the config file cf.
    """
    def __init__(self, configFile):
        self._config_file = configFile
        print("\n** Configuration Loading **\n")
        config = ConfigParser(self._config_file, self)
  
    """
        Simple toString method.
    """
    def toString(self):
        return "COMP0023 Routing Simulator";

    """
        Sets the duration for the simulation.
    """
    def set_stop_time(self, t):
        self._stop_time = t

    """
        Sets checkers to be called at the end of each simulated time unit.
    """ 
    def set_checkers(self, checkers_list):
        self._checkers = checkers_list

    """
        Sets verbosity level of the checkers.
    """
    def set_verbose(self, value):
        for checker in self._checkers:
            checker.setVerbose(value)

    """
        Adds the routers specified in the configuration to the 
        the simulator.
    """
    def add_routers(self, r):
        self._routers = {}
        count = 0
        for tr in r:
            self._routers[tr.getId()] = tr

    """
        Adds the events specified in the configuration to the 
        the simulator.
    """
    def add_events(self, e):
        self._events = []
        for te in e:
            print("Adding {}".format(te))
            self._events.append(te)

    """
        Adds the links specified in the configuration to the 
        the simulator and attaches them to the router objects.
    """
    def add_links(self, l):
        self._links = []

        for ml in l:
            self._links.append(ml)

        for i in range(len(self._links)):
            self._routers[self._links[i].getRouter(0)].addLink(self._links[i]) 
            self._routers[self._links[i].getRouter(1)].addLink(self._links[i])

    """
        Process the events scheduled for the time now
    """
    def process_events(self, now):
        event = None
        packet = None

        for count in range(len(self._events)):
            event = self._events[count]

            if ((event.getTime() <= now) and (event.getState() != True)):
                if (event.getOperation() == "send"):
                    packet = Packet(event.getArgument(0), event.getArgument(1))
                    packet.setType(PacketTypes.DATA.value)
                    if event.getNumberOfArguments() > 2:
                        packet.setTtl(event.getArgument(2))
                    self._packet_counter += 1
                    packet.setSequenceNumber(self._packet_counter)
                    packet.setSourcePort(5000+self._packet_counter)
                    self._routers[packet.getSource()].send(packet,description="Event: Sending one data packet from {} to {}".format(packet.getSource(),packet.getDestination()))

                elif (event.getOperation() == "uplink"):
                    for i in range(len(self._links)):
                       if (self._links[i].getInterface(0) == event.getArgument(0) and self._links[i].getInterface(1) == event.getArgument(1)):
                            print("Setting link {} UP\n".format(self._links[i]))
                            self._links[i].setState(True)

                elif (event.getOperation() == "downlink"):
                    for i in range(len(self._links)):
                        if (self._links[i].getInterface(0) == event.getArgument(0) and self._links[i].getInterface(1) == event.getArgument(1)):
                            print("Setting link {} DOWN\n".format(self._links[i]))
                            self._links[i].setState(False)

                elif (event.getOperation() == "dumpfib"):
                    if(event.getArgument(0) == "all"):
                        for rId in self._routers:
                            self._routers[rId].dumpForwardingTable()
                    else:
                        self._routers[event.getArgument(0)].dumpForwardingTable()

                elif (event.getOperation() == "dumpTrafficStats"):
                    print("event {}".format(event))
                    if (event.getArgument(0) == "all"):
                        for rId in self._routers:
                            self._routers[rId].dumpTrafficStats()
                    else:
                        self._routers[event.getArgument(0)].dumpTrafficStats()

                elif (event.getOperation() == "traceroute"):
                    self._routers[event.getArgument(0)].launchTraceroute(event.getArgument(1))

                elif (event.getOperation() == "stopOriginateIcmp"):
                    self._routers[event.getArgument(0)].stopOriginateICMPs(event.getArgument(1))

                else:
                    print("\n+++ ERROR: Simulator received event {} which is unable to handle: aborting +++\n".format(event))
                    sys.exit(1)

                self._events[count].setDone()

    """
        Process packets, move them from the out queue of one end of the link
        to the in queue of the other end. Do this for both ends.
    """
    def process_packets(self):
        for i in range(len(self._links)):
            self._links[i].movePackets()

    """
        Process routers, set the time step for now and then call 
        the go method of the router object.
    """
    def process_routers(self, now):
        for rId in self._routers:
            self._routers[rId].setTimeStep(now)
            self._routers[rId].go()

    """
        Checks if routers' FIB are what are supposed to be according to the topology
    """
    def check_iteration(self, time):
        for checker in self._checkers:
            checker.check(time)

    """
        Main loop of the simulator that runs through all the tasks at each
        time step. At each time step the Simulator carries out (in order)   
        event processing process_events, routers tasks       
        process_routers, packet forwarding process_packets
    """
    def main_loop(self):
        now = 1
        print("\n\n** Simulation **")
        while(now < self._stop_time):
            print("\n= Time {} =".format(now))
            self.process_events(now)
            self.process_routers(now)
            self.process_packets()
            self.check_iteration(now)
            now += 1
        self.check_completed()
        self.print_report()

    """
        Checks that all events have been processed.
    """
    def check_completed(self):
        unused_events = 0
        for i in range(len(self._events)):
            if (self._events[i].getState() != True):
                unused_events += 1

        if (unused_events > 0):
            print("\n+++ WARNING: stopping now but {} events not simulated! +++".format(unused_events))
    
    """
        Prints final report on the simulation.
        Prominently, it asks the checkers for a summary of their check results. 
    """    
    def print_report(self):
        print("\n\n** Simulation Report **\n")
        for checker in self._checkers:
            checker.printReport()
        print()

def main():
    parser = argparse.ArgumentParser(description='Routing Simulator for COMP0023.')
    parser.add_argument("-c", "--config_file", type=str, required=True,
                        help='Sets the configuration file for the simulation')
    parser.add_argument("-v", "--verbose", action='store_true', default=False, 
                        help='Runs the simulator in verbose mode', required=False)
    args = parser.parse_args()

    sim = Simulator(args.config_file)
    sim.set_verbose(args.verbose)
    sim.main_loop()

if __name__=="__main__":
    main()
