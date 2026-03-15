import threading
import time
import socket
from byte_queue import ByteQueue


class SchedulerReceiver (threading.Thread):
    """
    This thread listens on specified `port` for incoming packets and enqueues
    them. For each packet, it logs the arrival time, packet size, and backlog.

    Log format
    =
    elapsed time (us) <tab> pkt_len (bytes) <tab> buffer 0 backlog <tab> ...
    """

    def __init__(self, buffers: list[ByteQueue],
                 port: int, max_pkt_size: int, logfile: str):
        """
        :param buffers: shared buffers
        :param port: UDP port to bind for input
        :param max_pkt_size: maximum packet size allowed, in bytes
        :param logfile: path to write arrival log
        """
        super().__init__(daemon=True)
        self.buffers = buffers            # shared buffers
        self.port = port                  # listening port number
        self.max_pkt_size = max_pkt_size  # maximum packet size, in bytes
        self.log = open(logfile, "w")     # log file for packet arrival

    def run(self):
        sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        # Bind on all interfaces so traffic from any local NIC is accepted.
        sock.bind(("", self.port))

        buffers = self.buffers

        noDropped = 0    # the total number of dropped packets
        lastTime = None  # last received time
        while True:
            # Block until a packet is received.
            packet, _ = sock.recvfrom(65535)
            now = time.monotonic_ns()
            if lastTime is None:
                lastTime = now  # put elapsed=zero in the first line

            # Collecting data for logging
            elapsed = (now - lastTime)//1000  # time since last arrival, in us
            packet_size = len(packet)         # packet size, in bytes
            # Log arrival
            self.log.write(f"{elapsed}\t{packet_size}\t")
            for buffer in buffers:
                self.log.write(f"{buffer.backlog()}\t")
            self.log.write("\n")

            lastTime = now  # update last received time

            # Check if the packet size is appropriate
            if packet_size > self.max_pkt_size:
                noDropped += 1
                print(f"{noDropped}) Packet too large, dropped")
                continue

            # <-- student portion: classify packets into appropriate queues -->
            # Reference implementation always pick buffer 0
            buffer = buffers[0]

            # Enqueue if buffer has enough room; otherwise drop.
            if not buffer.try_put(packet):
                noDropped += 1
                print(f"{noDropped}) Buffer is full, dropped")
                continue
