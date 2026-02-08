import threading
import time
import socket


class TokenBucketReceiver (threading.Thread):
    """
    This thread listens on specified `port` for incoming packets and enqueues
    them. For each packet, it logs the arrival time, packet size, backlog,
    and token count.

    Log format
    =
    elapsed_us <tab> pkt_len <tab> backlog_bytes <tab> tokens
    """

    def __init__(self, sender, port: int, max_pkt_size: int, logfile: str):
        """
        :param sender: token bucket sender
        :param port: UDP port to bind for input
        :param max_pkt_size: maximum packet size allowed, in bytes
        :param logfile: path to write arrival log
        """
        super().__init__(daemon=True)
        self.sender = sender              # sender
        self.port = port                  # listening port number
        self.max_pkt_size = max_pkt_size  # maximum packet size, in bytes
        self.log = open(logfile, "w")     # log file for packet arrival

    def run(self):
        sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        sock.bind(("", self.port))

        # Grab `sender` members here so we can avoid pervasive `self.sender.*`
        dst_addr = self.sender.dst_addr   # destination address
        queue = self.sender.queue         # shared buffer queue
        bucket = self.sender.bucket       # shared token bucket
        snd_socket = self.sender.sock     # socket for sending packets
        snd_lock = self.sender.sock_lock  # mutex lock for `snd_socket`

        noDropped = 0    # the total number of dropped packets
        lastTime = None  # last received time
        while True:
            packet, _ = sock.recvfrom(65535)
            now = time.monotonic_ns()
            if lastTime is None:
                lastTime = now  # put elapsed=zero in the first line

            # collecting data for logging
            elapsed = (now - lastTime)//1000  # elasped time, in us
            packet_size = len(packet)      # packet size, in bytes
            backlog = queue.backlog()      # current backlog, in bytes
            tokens = bucket.getNoTokens()  # the number of tokens, in bytes
            # Record arrival:
            self.log.write(f"{elapsed}\t{packet_size}\t{backlog}\t{tokens}\n")

            lastTime = now  # update last received time

            # Check packet size first
            if packet_size > self.max_pkt_size:
                noDropped = 0
                print("Packet too large, dropped, total:", noDropped)
                continue

            # If buffer is empty, no packet is currently being sent, and there
            # are enough tokens, the received packet is sent immediately.
            #
            # Concurrency note:
            # It is ok to check whether `queue` is empty before locking
            # `snd_lock` because the receiver (`self`) is the only thread that
            # enqueues packets. So it is impossible for `queue` to become
            # non-empty while checking the other two conditions.
            if queue.is_empty() and snd_lock.acquire(blocking=False):
                try:
                    if bucket.removeTokens(packet_size):
                        snd_socket.sendto(packet, dst_addr)
                        continue  # packet sent, go to the next loop
                finally:
                    # Don't forget to release the lock
                    snd_lock.release()

            # `packet` is not sent, try adding it to the queue
            if not queue.try_put(packet):
                noDropped += 1
                print("Buffer is full, dropped, total:", noDropped)
