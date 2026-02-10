#!/usr/bin/env python3
import socket
import time
import argparse


def parse_poisson(parts):
    if len(parts) < 3:
        return None
    rel_ms = float(parts[1])
    size = int(parts[2])
    return rel_ms, size

def parse_video(parts):
    if len(parts) < 4:
        return None
    rel_ms = float(parts[1])
    size = int(parts[3])
    return rel_ms, size



def parse_ethernet(parts):
    if len(parts) >= 2:
        rel_ms = float(parts[0]) * 1000.0 
        size = int(parts[1])
        return rel_ms, size
    return None


def parse_line(tracefile, line):
    line = line.strip()
    if not line or line.startswith("#"):
        return None

    parts = line.split()

    # --- Part 2 ---
    if tracefile.endswith("poisson-lab2a.data"):
        return parse_poisson(parts)

    # --- Part 3-c ---
    if tracefile.endswith("movietrace.data"):
        return parse_video(parts)

    if tracefile.endswith("BC-pAug89.TL") or tracefile.endswith("BC-pAug89.TL.Z"):
        return parse_ethernet(parts)

    return parse_poisson(parts)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("dst_ip")
    ap.add_argument("dst_port", type=int)
    ap.add_argument("tracefile")
    ap.add_argument("--max-dgram", type=int, default=1480,
                    help="Max UDP payload (used in Part 3-c)")
    ap.add_argument("--limit", type=int, default=None,
                    help="Limit number of trace entries (used in Part 3-c)")
    args = ap.parse_args()

    rows = []
    with open(args.tracefile, "r") as f:
        for line in f:
            parsed = parse_line(args.tracefile, line)
            if parsed is None:
                continue
            rel_ms, size = parsed
            rows.append((rel_ms, size))
            if args.limit is not None and len(rows) >= args.limit:
                break

    if not rows:
        print("Trace file empty or unreadable.")
        return

    rows.sort(key=lambda x: x[0])

    sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    addr = (args.dst_ip, args.dst_port)

    # Timing setup
    t0_trace_ms = rows[0][0]
    t0 = time.monotonic()

    for rel_ms, size in rows:
        # Sleep until scheduled arrival time
        target_s = (rel_ms - t0_trace_ms) / 1000.0
        now_s = time.monotonic() - t0
        sleep_s = target_s - now_s
        if sleep_s > 0:
            time.sleep(sleep_s)

        # Part 2: packets already fit in one datagram
        # Part 3-c: split large frames into multiple datagrams
        remaining = size
        while remaining > 0:
            chunk = min(remaining, args.max_dgram)
            sock.sendto(b"a" * chunk, addr)
            remaining -= chunk

    sock.close()


if __name__ == "__main__":
    main()