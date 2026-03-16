#!/usr/bin/env python3
import argparse
import csv
import socket
import time


SOURCE_NAMES = {
    0x01: "poisson",
    0x02: "video",
}


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("listen_port", type=int)
    parser.add_argument("--outfile", default="tagged_sink.csv")
    args = parser.parse_args()

    sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    sock.bind(("", args.listen_port))

    with open(args.outfile, "w", newline="") as f:
        writer = csv.writer(f)
        writer.writerow([
            "time_s",
            "packet_size_bytes",
            "source_tag_hex",
            "source_name",
        ])
        start_ns = time.monotonic_ns()

        try:
            while True:
                packet, _ = sock.recvfrom(65535)
                now_s = (time.monotonic_ns() - start_ns) / 1e9
                tag = packet[0] if packet else -1
                writer.writerow([
                    now_s,
                    len(packet),
                    f"0x{tag:02x}" if tag >= 0 else "",
                    SOURCE_NAMES.get(tag, "unknown"),
                ])
                f.flush()
        except KeyboardInterrupt:
            pass
        finally:
            sock.close()


if __name__ == "__main__":
    main()
