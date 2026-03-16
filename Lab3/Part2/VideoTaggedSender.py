#!/usr/bin/env python3
import argparse
import socket
import time


TAG_BYTE = 0x02
MAX_PAYLOAD_BYTES = 1480
MAX_FRAME_CHUNK_BYTES = MAX_PAYLOAD_BYTES - 1


def parse_video_line(line: str):
    line = line.strip()
    if not line or line.startswith("#"):
        return None

    parts = line.split()
    if len(parts) < 4:
        return None

    rel_ms = float(parts[1])
    frame_size = int(parts[3])
    return rel_ms, frame_size


def build_fragment(chunk_size: int) -> bytes:
    return bytes([TAG_BYTE]) + (b"v" * chunk_size)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("dest_ip")
    parser.add_argument("dest_port", type=int)
    parser.add_argument("tracefile", nargs="?", default="Lab2/part1/movietrace.data")
    parser.add_argument("--limit", type=int, default=None)
    args = parser.parse_args()

    rows = []
    with open(args.tracefile, "r") as f:
        for line in f:
            parsed = parse_video_line(line)
            if parsed is None:
                continue
            rows.append(parsed)
            if args.limit is not None and len(rows) >= args.limit:
                break

    if not rows:
        return

    rows.sort(key=lambda row: row[0])

    sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    start_monotonic = time.monotonic()
    first_rel_ms = rows[0][0]

    for rel_ms, frame_size in rows:
        target_s = (rel_ms - first_rel_ms) / 1000.0
        sleep_s = target_s - (time.monotonic() - start_monotonic)
        if sleep_s > 0:
            time.sleep(sleep_s)

        remaining = frame_size
        while remaining > 0:
            chunk_size = min(remaining, MAX_FRAME_CHUNK_BYTES)
            sock.sendto(
                build_fragment(chunk_size),
                (args.dest_ip, args.dest_port),
            )
            remaining -= chunk_size

    sock.close()


if __name__ == "__main__":
    main()
