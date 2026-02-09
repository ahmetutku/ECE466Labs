#!/usr/bin/env python3
"""
ECE466 Lab 2a - UDP receiver/sink (Part 2 / used for Part 3)

Logs each arrival as:
  elapsed_us <TAB> pkt_len

Usage:
  python3 Receiver_fixed.py <listen_port> <outfile>

Example (sink for token bucket forwarding to 5555):
  python3 Receiver_fixed.py 5555 sink.log
"""
import socket
import sys
import time

def main():
    if len(sys.argv) != 3:
        print(f"Usage: {sys.argv[0]} <listen_port> <outfile>")
        sys.exit(1)

    listen_port = int(sys.argv[1])
    outfile = sys.argv[2]

    sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    sock.bind(("", listen_port))

    print(f"Waiting for UDP on port {listen_port} ... (Ctrl+C to stop)")

    t0 = None
    with open(outfile, "w") as f:
        f.write("elapsed_us\tpkt_len\n")
        try:
            while True:
                data, addr = sock.recvfrom(65535)  # don't truncate
                now = time.monotonic_ns()
                if t0 is None:
                    t0 = now
                elapsed_us = (now - t0) // 1000
                f.write(f"{elapsed_us}\t{len(data)}\n")
        except KeyboardInterrupt:
            pass
        finally:
            sock.close()

if __name__ == "__main__":
    main()