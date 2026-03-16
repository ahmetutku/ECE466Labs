import argparse
import threading

# imports from other .py in the same directory
from scheduler_sender import SchedulerSender
from scheduler_receiver import SchedulerReceiver
from byte_queue import ByteQueue
from evaluation_logger import EvaluationLogger
from priority_stats import PriorityStats

FIFO_BUFFER_BYTES = 100_000
FIFO_LINK_BPS = 20_000_000


class PacketScheduler:
    def __init__(self, in_port: int, out_ip, out_port: int,
                 link_capacity: float, max_packet_size: int,
                 buffer_capacities: list[int], fileName):
        nonempty = threading.Semaphore(0)
        high_capacity = buffer_capacities[0] if len(buffer_capacities) >= 1 else FIFO_BUFFER_BYTES
        low_capacity = buffer_capacities[1] if len(buffer_capacities) >= 2 else FIFO_BUFFER_BYTES
        fifo_rate = link_capacity if link_capacity else FIFO_LINK_BPS
        buffers = [
            ByteQueue(high_capacity, nonempty),
            ByteQueue(low_capacity, nonempty),
        ]
        eval_logger = EvaluationLogger(fileName)
        priority_stats = PriorityStats()
        self.sender = SchedulerSender(
            buffers, fifo_rate, (out_ip, out_port), eval_logger, priority_stats)
        self.receiver = SchedulerReceiver(
            buffers, in_port, max_packet_size, eval_logger, priority_stats)
        self.priority_stats = priority_stats

    def start(self):
        self.sender.start()
        self.receiver.start()

        try:
            self.sender.join()
            self.receiver.join()
        except KeyboardInterrupt:
            pass
        finally:
            print("Priority scheduler summary:")
            for line in self.priority_stats.summary_lines():
                print(line)


# ---------------- Main function ----------------
# You do not need to edit this portion. Run `python3 packet_scheduler.py -h`
# to see help information of this script
if __name__ == "__main__":
    """CLI: create scheduler, receiver, and sender threads and start shaping."""
    parser = argparse.ArgumentParser(description="UDP token-bucket shaper")
    parser.add_argument("in_port", type=int, help="UDP port to listen on")
    parser.add_argument("out_ip", type=str, help="Destination IP address")
    parser.add_argument("out_port", type=int, help="Destination UDP port")
    parser.add_argument("link_capacity", type=int, help="sender rate, in bps")
    parser.add_argument("buffer_capacities", type=int, nargs="+",
                        help="buffer capacities of each queue, in bytes")

    parser.add_argument("--max-packet-size", type=int, default=1480,
                        help="Maximum datagram size, in bytes (default: 1480)")
    parser.add_argument("--logfile", type=str, default="arrivals.log",
                        help="Arrival log file (default: arrivals.log)")
    args = parser.parse_args()

    packet_scheduler = PacketScheduler(
        args.in_port, args.out_ip, args.out_port,
        args.link_capacity, args.max_packet_size,
        args.buffer_capacities, args.logfile
    )
    packet_scheduler.start()
