#!/usr/bin/env python3
import argparse
import socket
import time


TAG_BYTE = 0x01
MAX_PAYLOAD_BYTES = 1480


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


def build_payload(packet_size: int) -> bytes:
    if packet_size <= 0:
        raise ValueError("Packet size must be positive")
    if packet_size > MAX_PAYLOAD_BYTES:
        raise ValueError(
            f"Poisson packet size {packet_size} exceeds {MAX_PAYLOAD_BYTES} bytes"
        )
    if packet_size == 1:
        return bytes([TAG_BYTE])
    return bytes([TAG_BYTE]) + (b"x" * (packet_size - 1))


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("dest_ip")
    parser.add_argument("dest_port", type=int)
    parser.add_argument(
        "tracefile",
        nargs="?",
        default="Lab3/Part1/Part1a/poisson3.data",
    )
    args = parser.parse_args()

    sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    prev_timestamp_us = None

    with open(args.tracefile, "r") as f:
        for line in f:
            line = line.strip()
            if not line or line.startswith("#"):
                continue

            parts = line.split()
            delay_us, packet_size, prev_timestamp_us = parse_trace_line(
                parts, prev_timestamp_us
            )
            time.sleep(delay_us / 1_000_000)
            sock.sendto(build_payload(packet_size), (args.dest_ip, args.dest_port))

    sock.close()


if __name__ == "__main__":
    main()
