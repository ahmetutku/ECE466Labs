import argparse
import threading

# imports from other .py in the same directory
from scheduler_sender import SchedulerSender
from scheduler_receiver import SchedulerReceiver
from byte_queue import ByteQueue


class PacketScheduler:
    def __init__(self, in_port: int, out_ip, out_port: int,
                 link_capacity: float, max_packet_size: int,
                 buffer_capacities: list[int], fileName):
        nonempty = threading.Semaphore(0)
        buffers = [ByteQueue(cap, nonempty) for cap in buffer_capacities]
        self.sender = SchedulerSender(
            buffers, link_capacity, (out_ip, out_port))
        self.receiver = SchedulerReceiver(
            buffers, in_port, max_packet_size, fileName)

    def start(self):
        self.sender.start()
        self.receiver.start()

        self.sender.join()
        self.receiver.join()


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
