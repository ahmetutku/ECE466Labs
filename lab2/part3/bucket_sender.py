import threading
import time
import socket


class TokenBucketSender(threading.Thread):
    """
    This thread removes and sends packets from buffer to a given address.
    Packets are sent only when there are enough tokens in the `token_bucket`.
    """

    def __init__(self, queue, token_bucket, dst_addr):
        """
        :param queue: shared ByteQueue for outgoing packets
        :param token_bucket: the token bucket controlling send timing
        :param dst_addr: the destination tuple for UDP sendto
        """
        super().__init__(daemon=True)
        self.queue = queue
        self.bucket = token_bucket
        self.dst_addr: socket._Address = dst_addr  # destination address
        # outbound socket for sending packets
        self.sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        # lock for permission to transmit packets
        self.sock_lock = threading.Lock()

    def run(self):
        while True:
            # If buffer is non-empty, get the first packet without removing it
            if packet := self.queue.peek():
                # There is a packet. If we have enough tokens, `remove` will
                # succeed, and we can send the packet right away.
                packet_size = len(packet)
                if self.bucket.removeTokens(packet_size):
                    self.queue.get()
                    with self.sock_lock:
                        self.sock.sendto(packet, self.dst_addr)
                else:
                    # We have insufficient tokens.
                    # Get expected time when there will be enough tokens,
                    wait_s: float = self.bucket.getWaitingTime(packet_size)/1e3
                    # and sleep for that time.
                    time.sleep(wait_s)
            else:
                # There is no packet, wait for a packet to become available
                self.queue.wait()
