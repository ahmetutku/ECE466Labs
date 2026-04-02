from queue import Queue
from threading import Thread
from time import monotonic_ns, sleep
import argparse
import socket
import struct

Packet = tuple[float, bytes, tuple[str, int]]  # time (ns), data, destination


class Receiver(Thread):
    """Consumes raw UDP datagrams and enqueues validated packets."""

    def __init__(self, port: int, qin: Queue[Packet]):
        super().__init__(daemon=True)
        self.qin = qin
        self.port = port

    def run(self):
        qin = self.qin
        portStruct = struct.Struct('>H')
        sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        sock.bind(("0.0.0.0", self.port))

        # Minimize the amount of work per loop for accurate arrival time.
        # Leave the calculation of transmission time to Shaper.
        noDropped = 0
        while True:
            # Wait for a packet, and immediately get arrival time
            packet, (ip, _) = sock.recvfrom(65535)
            arrival_time = monotonic_ns()
            pkt_len = len(packet)

            # Check that packet has valid size and port number.
            if pkt_len < 2:
                noDropped += 1
                print(f"{noDropped}) Packet is too small, dropped")
            else:
                # packet format: [port (hi), port (lo)]
                port = portStruct.unpack_from(packet, 0)[0]
                qin.put((arrival_time, packet, (ip, port)))


class Shaper(Thread):
    """Converts pkt+arrival time from `qin` to pkt+tx time for `qout`"""

    def __init__(self, burst: float, rate: float, delay: float,
                 qin: Queue[Packet], qout: Queue[Packet]):
        super().__init__(daemon=True)
        self.burst = burst
        self.rate_recp = 1/rate
        self.delay = delay
        self.qin = qin
        self.qout = qout
        # TB is full if packet arrival is this late from its `tx_time`.
        self.max_lag = burst/rate

    def run(self):
        burst = self.burst
        rate_recp = self.rate_recp
        delay = self.delay
        qin = self.qin
        qout = self.qout
        max_lag = self.max_lag

        start_time = float('-inf')  # The last time when TB is full.
        # (Total tokens consumed since `start_time`) - burst. The `-burst`
        # term minimizes the addition/subtraction needed in the loop.
        consumed = -burst
        while True:
            arrival_time, pkt, dst = qin.get()
            pkt_len = len(pkt)
            consumed += pkt_len
            # The time when TB has just enough token to transmit
            tx_time = start_time + consumed*rate_recp
            if tx_time + max_lag <= arrival_time:
                # Packet arrives late, and TB is full. Reset the clock.
                start_time = arrival_time
                consumed = pkt_len - burst
            # Ensure causality (arrival <= tx), and add the constant delay.
            qout.put((max(tx_time, arrival_time) + delay, pkt, dst))


class Sender(Thread):
    """Sends packets at their scheduled transmission time over UDP."""

    def __init__(self, queue: Queue[Packet]):
        super().__init__(daemon=True)
        self.queue = queue

    def run(self):
        # Waits until tx_time, then sends immediately for tighter schedule control.
        queue = self.queue
        sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        while True:
            tx_time, pkt, dst = queue.get()
            # Sleep, then busy wait until transmission time.
            if (wait := (tx_time - monotonic_ns())/1e9 - 1e-3) >= 0:
                sleep(wait)
            while tx_time > monotonic_ns():
                pass
            sock.sendto(pkt, dst)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        description="UDP delay-burst-rate blackbox")
    parser.add_argument("burst", type=float, help="burst parameter, in bits")
    parser.add_argument("rate", type=float, help="long term rate, in kbps")
    parser.add_argument("delay", type=float, help="additional delay, in ms")

    parser.add_argument("--inport", type=int, default=4444,
                        help="incoming UDP port")
    args = parser.parse_args()

    qin = Queue[Packet]()
    qout = Queue[Packet]()

    # Convert to B and ns internally to match `monotonic_ns` and `len(packet)`
    burst = args.burst/8    # B
    rate = args.rate/8e6    # B/ns
    delay = args.delay*1e6  # ns

    receiver = Receiver(args.inport, qin)
    shaper = Shaper(burst, rate, delay, qin, qout)
    sender = Sender(qout)

    receiver.start()
    shaper.start()
    sender.run()
