import argparse
import sys
import threading
import time

# imports from other .py in the same directory
from bucket_sender import TokenBucketSender
from bucket_receiver import TokenBucketReceiver
from byte_queue import ByteQueue


class TokenBucket:
    """
    Token bucket implementation for shaping the network traffic.
    For efficiency, tokens are computed lazily on demand instead of on a timer.
    """

    def __init__(self, size: float, rate: float):
        """
        Create a token bucket with bucket `size` and token refill `rate`.

        :param size: maximum tokens allowed in the bucket, in tokens
        :param rate: token refill rate in tokens/second
        """
        self.capacity = size  # the bucket capacity, in tokens
        self.rate = rate      # the bucket filling rate, in tokens/second
        self.tokens = size    # the current number of tokens, in tokens
        self.last = time.monotonic_ns()  # last update time, in nanoseconds
        self.lock = threading.Lock()

    def updateNoTokens(self):
        """
        Update the current number of tokens (self.tokens).
        Tokens are capped at the bucket size (excess tokens are discarded).
        """
        # <-- student portion: implement this -->
        # This function is never called by the sender or the receiver.
        # It is only used to implement TokenBucket's other three functions.
        now = time.monotonic_ns()
        dt_ns = now - self.last
        if dt_ns <= 0:
            return

        dt_s = dt_ns / 1e9
        self.tokens = min(self.capacity, self.tokens + self.rate * dt_s)
        self.last = now

    def getWaitingTime(self, target: float):
        """Calculate waiting time (ms) until `target` tokens are available."""
        with self.lock:
            # <-- student portion: implement this -->
            self.updateNoTokens()
            target = float(target)
            if self.tokens >= target:
                return 0.0
            if self.rate <= 0:
                # never fills; "infinite" wait
                return float("inf")
            needed = target - self.tokens  # tokens
            wait_s = needed / self.rate
            return wait_s * 1000.0

    def getNoTokens(self):
        """The current number of tokens"""
        with self.lock:
            # <-- student portions: implement this -->
            self.updateNoTokens()
            return self.tokens

    def removeTokens(self, target: int):
        """
        If `target` tokens are available, remove the tokens and return True.
        Otherwise, return False.
        """
        with self.lock:
            self.updateNoTokens()
            target = float(target)
            if self.tokens >= target:
                self.tokens -= target
                return True
            return False
# ---------------- Main function ----------------
# You do not need to edit this portion. Run `python3 token_bucket.py -h` to see
# help information of this script
if __name__ == "__main__":
    """CLI: create bucket, receiver, and sender threads and start shaping."""
    parser = argparse.ArgumentParser(description="UDP token-bucket shaper")
    parser.add_argument("in_port", type=int, help="UDP port to listen on")
    parser.add_argument("out_ip", type=str, help="Destination IP address")
    parser.add_argument("out_port", type=int, help="Destination UDP port")
    parser.add_argument("bucket_size", type=int,
                        help="Token bucket size, in bytes")
    parser.add_argument("bucket_rate", type=int,
                        help="Token generation rate, in bytes/sec")

    parser.add_argument("--max-packet-size", type=int, default=1480,
                        help="Maximum UDP packet size, in bytes")
    parser.add_argument("--buffer-capacity", type=int, default=200_000,
                        help="Buffer capacity, in bytes")
    parser.add_argument("--logfile", type=str, default="arrivals.log",
                        help="Arrival log file")
    args = parser.parse_args()

    if args.bucket_size < args.max_packet_size:
        print("Bucket size should not be smaller than the maximum packet size!", file=sys.stderr)
        print("Token bucket will be constructed with given parameters, but arrival of" +
              "packet with size gratar than bucket size will prevent sending of any further packets.",
              file=sys.stderr)

    buffer = ByteQueue(args.buffer_capacity)
    bucket = TokenBucket(args.bucket_size, args.bucket_rate)
    sender = TokenBucketSender(buffer, bucket, (args.out_ip, args.out_port))
    receiver = TokenBucketReceiver(sender, args.in_port, args.max_packet_size,
                                   args.logfile)

    sender.start()
    receiver.start()
    sender.join()
    receiver.join()
