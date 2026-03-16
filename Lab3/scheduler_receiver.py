import threading
import socket
from byte_queue import ByteQueue
from evaluation_logger import EvaluationLogger
from priority_stats import PriorityStats

HIGH_PRIORITY_TAG = 0x02
LOW_PRIORITY_TAG = 0x01


class SchedulerReceiver (threading.Thread):
    """
    This thread listens on specified `port` for incoming packets and enqueues
    them. For each packet, it logs the arrival time, packet size, and backlog.

    Log format
    =
    elapsed time (us) <tab> pkt_len (bytes) <tab> buffer 0 backlog <tab> ...
    """

    def __init__(self, buffers: list[ByteQueue],
                 port: int, max_pkt_size: int, eval_logger: EvaluationLogger,
                 priority_stats: PriorityStats):
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
        self.eval_logger = eval_logger
        self.priority_stats = priority_stats

    def run(self):
        sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        # Bind on all interfaces so traffic from any local NIC is accepted.
        sock.bind(("", self.port))

        buffers = self.buffers

        noDropped = 0    # the total number of dropped packets
        while True:
            # Block until a packet is received.
            packet, _ = sock.recvfrom(65535)
            packet_size = len(packet)         # packet size, in bytes

            # Check if the packet size is appropriate
            if packet_size > self.max_pkt_size:
                noDropped += 1
                self.eval_logger.log_arrival(packet_size, 0, dropped=True)
                print(f"{noDropped}) Packet too large, dropped")
                continue

            tag = packet[0] if packet else -1
            is_high = tag == HIGH_PRIORITY_TAG
            if tag == LOW_PRIORITY_TAG:
                is_high = False
            buffer_index = 0 if is_high else 1
            buffer = buffers[buffer_index]
            backlog_bytes = buffer.backlog()
            self.priority_stats.note_classified(is_high)
            record = self.eval_logger.log_arrival(
                packet_size, backlog_bytes, dropped=False
            )
            record["data"] = packet
            record["is_high"] = is_high
            record["source_tag"] = tag

            # Enqueue if buffer has enough room; otherwise drop.
            if not buffer.try_put(record):
                noDropped += 1
                self.eval_logger.log_drop(record)
                self.priority_stats.note_dropped(is_high)
                print(
                    f"{noDropped}) Buffer full: dropped {packet_size}-byte "
                    f"{'high' if is_high else 'low'} packet "
                    f"(occupancy={buffer.backlog()} / {buffer.MAX_BYTES} bytes)"
                )
                continue
