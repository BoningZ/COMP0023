#! /usr/bin/python3


# TODO: add hereafter (as a comment) the description of your design according to specifications of the "Step-back task" in the CW handout.
# <a few sentences>


import sys, socket, hashlib, time
from optparse import OptionParser, OptionValueError
from collections import defaultdict

# default parameters
default_ip = '127.0.0.1'
default_port = 50023

cwnd = 1  # Congestion window, default is 1 if not set by client
ssthresh = 10  # Slow start threshold for congestion control
send_base = 0  # Base sequence number of unacknowledged packets
next_seq_num = 0  # Next sequence number to send
retransmit_timer = 0.5  # Timeout for retransmission in seconds
ack_counts = defaultdict(int)  # Counter for duplicate ACKs

# Helper functions #

def get_checksum(msg):
  return hashlib.md5(msg.encode()).hexdigest()

def check_port(option, opt_str, value, parser):
  if value < 32768 or value > 61000:
    raise OptionValueError("need 32768 <= port <= 61000")
  parser.values.port = value

def check_address(option, opt_str, value, parser):
  value_array = value.split(".")
  if len(value_array) < 4 or \
     int(value_array[0]) < 0 or int(value_array[0]) > 255 or \
     int(value_array[1]) < 0 or int(value_array[1]) > 255 or \
     int(value_array[2]) < 0 or int(value_array[2]) > 255 or \
     int(value_array[3]) < 0 or int(value_array[3]) > 255:
    raise OptionValueError("IP address must be specified as [0-255].[0-255].[0-255].[0-255]")
  parser.values.ip = value

# Main #

if __name__ == "__main__":
  # parse CLI arguments
  # NOTE: do NOT remove support for the following options
  parser = OptionParser()
  parser.add_option("-p", "--port", dest="port", type="int", action="callback",
                    callback=check_port, metavar="PORTNO", default=default_port,
                    help="UDP port to listen on (default: {})".format(default_port))
  parser.add_option("-a", "--address", dest="ip", type="string", action="callback",
                    callback=check_address, metavar="IPNO", default=default_ip,
                    help="IP port to listen on (default: {})".format(default_ip))
  (options, args) = parser.parse_args()
  own_ip = options.ip
  own_port = options.port

  # create a socket for packet exchanges with the clients
  sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
  own_address = (own_ip, own_port)
  sock.bind(own_address)

  # print that we are ready
  # NOTE: do NOT remove the following print
  print("%s: listening on IP %s and UDP port %d" % (sys.argv[0], own_ip, own_port))
  sys.stdout.flush()

  # extract content of file to transfer 
  content = ["FILENAME server_file.txt\n"]  # Treat the filename as the first line of content
  with open("server_file.txt") as f:
    content.extend(f.readlines())

  # wait for GETs from clients, and transfer file content after each request
    while True:
      (data, sender_address) = sock.recvfrom(512)
      client_address = data.decode().split("]")[0] + "]"
      req = data.decode().split("]")[1].strip()
      print("Received {}".format(data))

      if req.startswith("SET-CWND"):
        cwnd = int(req.split()[-1])  # Adjust initial congestion window size
        print("Congestion window set to:", cwnd)
        continue

      elif req == "GET":
        send_base = 0
        next_seq_num = 0

        while send_base < len(content):
          # Send packets within the window
          while next_seq_num < send_base + cwnd and next_seq_num < len(content):
            msg = "{} {}:{}|{}".format(client_address, next_seq_num, content[next_seq_num].strip(), get_checksum(content[next_seq_num].strip()))
            sock.sendto(msg.encode(), sender_address)
            print(f"Sent packet {next_seq_num}")
            next_seq_num += 1
            time.sleep(0.01)  # Slight delay to prevent overwhelming network

          # Wait for ACK or timeout for retransmission
          sock.settimeout(retransmit_timer)
          try:
            (ack_data, _) = sock.recvfrom(512)
            ack_msg = ack_data.decode().split(" ")
            if ack_msg[1] == "ACK":
              ack_num = int(ack_msg[2])

              # Fast retransmit on three duplicate ACKs
              if ack_num < next_seq_num:
                ack_counts[ack_num] += 1
                if ack_counts[ack_num] >= 3:
                  print(f"Fast retransmitting packet {ack_num + 1}")
                  resend_msg = "{} {}:{}|{}".format(client_address, ack_num + 1, content[ack_num + 1].strip(), get_checksum(content[ack_num + 1].strip()))
                  sock.sendto(resend_msg.encode(), sender_address)
                  ack_counts[ack_num] = 0  # Reset count after fast retransmit
                  # Enter congestion control: halve cwnd and set ssthresh
                  ssthresh = max(cwnd // 2, 1)
                  cwnd = ssthresh  # Adjust cwnd for fast recovery
                  print(f"Entering fast recovery, ssthresh set to {ssthresh}")

              if ack_num >= send_base:
                # Update send_base and clear ACK counters
                send_base = ack_num + 1
                ack_counts.clear()

                # Adjust cwnd based on congestion control state
                if cwnd < ssthresh:
                  # Slow start phase (exponential growth)
                  cwnd *= 2
                else:
                  # Congestion avoidance phase (linear growth)
                  cwnd += 1 / cwnd
                print(f"cwnd increased to {cwnd}")

          except socket.timeout:
            # Timeout retransmit for the base packet
            resend_msg = "{} {}:{}|{}".format(client_address, send_base, content[send_base].strip(), get_checksum(content[send_base].strip()))
            sock.sendto(resend_msg.encode(), sender_address)
            print(f"Timeout retransmitting packet {send_base}")
            # On timeout, set ssthresh and reset cwnd
            ssthresh = max(cwnd // 2, 1)
            cwnd = 1
            print(f"Timeout detected, ssthresh set to {ssthresh}, cwnd reset to {cwnd}")

          # Handle congestion dropped packets by reducing cwnd
          if "Congest-dropped" in data.decode():
            cwnd = max(1, cwnd // 2)
            print(f"Congestion detected, reducing cwnd to {cwnd}")

        # Send FIN packet after all data is sent
        fin_msg = "{} FIN".format(client_address)
        sock.sendto(fin_msg.encode(), sender_address)
        print("Sent FIN packet")

      elif req == "ACK FIN":
        # Handle the acknowledgment of the FIN packet
        sock.sendto("{} ACK".format(client_address).encode(), sender_address)
        print("Connection closed with client")