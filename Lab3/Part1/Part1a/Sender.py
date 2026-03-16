#!/usr/bin/env python3
import argparse
import socket
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
    parser = argparse.ArgumentParser()
    parser.add_argument("dest_ip")
    parser.add_argument("dest_port", type=int)
    parser.add_argument("tracefile")
    parser.add_argument("--source-id", type=int, default=None)
    args = parser.parse_args()

    dest_ip = args.dest_ip
    dest_port = args.dest_port
    tracefile = args.tracefile

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

            if args.source_id is None:
                payload = b"x" * pkt_size
            elif pkt_size <= 1:
                payload = bytes([args.source_id & 0xFF])
            else:
                payload = bytes([args.source_id & 0xFF]) + (b"x" * (pkt_size - 1))
            sock.sendto(payload, (dest_ip, dest_port))

    sock.close()

if __name__ == "__main__":
    main()
