import threading
import time
import socket
from byte_queue import ByteQueue
from Lab3.Part1.part1bc.evaluation_logger import EvaluationLogger


class SchedulerSender(threading.Thread):
    """
    This thread dequeues packets selected by the scheduler and sends them
    to the configured UDP destination at the configured pacing rate.
    """

    def __init__(self, buffers: list[ByteQueue], rate: float, dst_addr,
                 eval_logger: EvaluationLogger):
        """
        :param buffers: shared buffers
        :param rate: assigned transmission rate, in bps
        :param dst_addr: the destination tuple for UDP sendto
        """
        super().__init__(daemon=True)
        self.buffers = buffers  # shared buffers
        self.rate = rate        # transmission rate
        self.dst_addr: socket._Address = dst_addr  # destination address
        self.eval_logger = eval_logger

    def run(self):
        # Extract `self` members
        buffers = self.buffers
        nonempty = buffers[0].nonempty  # the number of non-empty buffers
        rate_recp = 8e9/self.rate       # 1/rate, in ns / byte
        dst_addr = self.dst_addr
        eval_logger = self.eval_logger
        # outbound socket for sending packets
        sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        # completion time of the previous packet
        prev_complete = time.monotonic_ns()

        while True:
            # Wait until at least one buffer is nonempty (acquire returns).
            nonempty.acquire()
            arrival_time = time.monotonic_ns()
            nonempty.release()  # Return the token to keep the value accurate.

            # FIFO scheduler: the single shared queue preserves arrival order.
            record = buffers[0].get()
            packet = record["data"]
            packet_length = record["packet_size_bytes"]

            # If this packet arrives before the previous one completes, wait
            while time.monotonic_ns() <= prev_complete:
                wait_s = (prev_complete - time.monotonic_ns()) / 1e9
                # Sleep until the last ms, then busy waiting because
                # busy waiting has higher precision than `sleep`
                if wait_s >= 1e-3:
                    time.sleep(wait_s)

            # Send, and update completion time
            tx_start_ns = max(arrival_time, prev_complete)
            departure_ns = tx_start_ns + int(packet_length * rate_recp)
            sock.sendto(packet, dst_addr)
            eval_logger.log_departure(record, departure_ns)
            prev_complete = departure_ns
