#!/usr/bin/env python3
import socket
import sys
import time


def parse_trace_line(parts, prev_timestamp_us):
    if len(parts) == 1:
        return int(parts[0]), 1000, prev_timestamp_us

    if len(parts) == 2:
        return int(parts[0]), int(parts[1]), prev_timestamp_us

    timestamp_us = int(parts[1])
    packet_size = int(parts[2])
    if prev_timestamp_us is None:
        delay_us = 0
    else:
        delay_us = max(0, timestamp_us - prev_timestamp_us)
    return delay_us, packet_size, timestamp_us


def main():
    if len(sys.argv) != 4:
        print(f"Usage: {sys.argv[0]} <dest_ip> <dest_port> <tracefile>")
        sys.exit(1)

    dest_ip = sys.argv[1]
    dest_port = int(sys.argv[2])
    tracefile = sys.argv[3]

    sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    prev_timestamp_us = None

    with open(tracefile, "r") as f:
        for line in f:
            line = line.strip()

            if not line or line.startswith("#"):
                continue

            parts = line.split()
            delay_us, pkt_size, prev_timestamp_us = parse_trace_line(
                parts, prev_timestamp_us
            )

            # wait before sending next packet
            time.sleep(delay_us / 1_000_000)

            payload = b"x" * pkt_size
            sock.sendto(payload, (dest_ip, dest_port))

    sock.close()

if __name__ == "__main__":
    main()
