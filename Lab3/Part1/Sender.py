#!/usr/bin/env python3
import socket
import sys
import time

def main():
    if len(sys.argv) != 4:
        print(f"Usage: {sys.argv[0]} <dest_ip> <dest_port> <tracefile>")
        sys.exit(1)

    dest_ip = sys.argv[1]
    dest_port = int(sys.argv[2])
    tracefile = sys.argv[3]

    sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)

    with open(tracefile, "r") as f:
        for line in f:
            line = line.strip()

            if not line or line.startswith("#"):
                continue

            parts = line.split()

            # Case 1: only delay provided
            if len(parts) == 1:
                delay_us = int(parts[0])
                pkt_size = 1000

            # Case 2: delay and packet size
            else:
                delay_us = int(parts[0])
                pkt_size = int(parts[1])

            # wait before sending next packet
            time.sleep(delay_us / 1_000_000)

            payload = b"x" * pkt_size
            sock.sendto(payload, (dest_ip, dest_port))

    sock.close()

if __name__ == "__main__":
    main()