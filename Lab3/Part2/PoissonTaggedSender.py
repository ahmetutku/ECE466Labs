#!/usr/bin/env python3
import argparse
import socket
import time


DEFAULT_TAG_BYTE = 0x01
MAX_PAYLOAD_BYTES = 1480


def parse_trace_line(parts, prev_timestamp_us):
    if len(parts) == 1:
        delay_us = int(parts[0])
        timestamp_us = delay_us if prev_timestamp_us is None else prev_timestamp_us + delay_us
        return timestamp_us, 1000

    if len(parts) == 2:
        delay_us = int(parts[0])
        packet_size = int(parts[1])
        timestamp_us = delay_us if prev_timestamp_us is None else prev_timestamp_us + delay_us
        return timestamp_us, packet_size

    timestamp_us = int(parts[1])
    packet_size = int(parts[2])
    return timestamp_us, packet_size


def build_payload(packet_size: int, tag_byte: int) -> bytes:
    if packet_size <= 0:
        raise ValueError("Packet size must be positive")
    if packet_size > MAX_PAYLOAD_BYTES:
        raise ValueError(
            f"Poisson packet size {packet_size} exceeds {MAX_PAYLOAD_BYTES} bytes"
        )
    if packet_size == 1:
        return bytes([tag_byte & 0xFF])
    return bytes([tag_byte & 0xFF]) + (b"x" * (packet_size - 1))


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("dest_ip")
    parser.add_argument("dest_port", type=int)
    parser.add_argument(
        "tracefile",
        nargs="?",
        default="Lab3/Part1/Part1a/poisson3.data",
    )
    parser.add_argument("--tag-byte", type=lambda v: int(v, 0), default=DEFAULT_TAG_BYTE)
    args = parser.parse_args()

    sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    prev_timestamp_us = None
    rows = []

    with open(args.tracefile, "r") as f:
        for line in f:
            line = line.strip()
            if not line or line.startswith("#"):
                continue

            parts = line.split()
            timestamp_us, packet_size = parse_trace_line(
                parts, prev_timestamp_us
            )
            prev_timestamp_us = timestamp_us
            rows.append((timestamp_us, packet_size))

    if not rows:
        sock.close()
        return

    first_timestamp_us = rows[0][0]
    start_monotonic = time.monotonic()

    for timestamp_us, packet_size in rows:
        target_s = (timestamp_us - first_timestamp_us) / 1_000_000
        sleep_s = target_s - (time.monotonic() - start_monotonic)
        if sleep_s > 0:
            time.sleep(sleep_s)
        sock.sendto(
            build_payload(packet_size, args.tag_byte),
            (args.dest_ip, args.dest_port),
        )

    sock.close()


if __name__ == "__main__":
    main()
