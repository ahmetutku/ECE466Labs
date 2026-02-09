#!/usr/bin/env python3
import socket
import sys
import time

def load_trace(path: str):
    rows = []
    with open(path, "r") as f:
        for line in f:
            line = line.strip()
            if not line or line.startswith("#"):
                continue
            parts = line.split()
            if len(parts) < 3:
                continue
            seq = int(parts[0])
            rel_ms = float(parts[1])
            size = int(parts[2])
            rows.append((seq, rel_ms, size))
    rows.sort(key=lambda x: x[1])
    return rows

def main():
    if len(sys.argv) != 4:
        print(f"Usage: {sys.argv[0]} <dst_ip> <dst_port> <tracefile>")
        sys.exit(1)

    dst_ip = sys.argv[1]
    dst_port = int(sys.argv[2])
    tracefile = sys.argv[3]

    rows = load_trace(tracefile)
    if not rows:
        print("Trace file empty or unreadable.")
        sys.exit(1)

    sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    addr = (dst_ip, dst_port)

    t0_trace_ms = rows[0][1]
    t0 = time.monotonic()

    for _, rel_ms, size in rows:
        target_s = (rel_ms - t0_trace_ms) / 1000.0
        now_s = time.monotonic() - t0
        sleep_s = target_s - now_s
        if sleep_s > 0:
            time.sleep(sleep_s)

        sock.sendto(b"a" * size, addr)

    sock.close()

if __name__ == "__main__":
    main()