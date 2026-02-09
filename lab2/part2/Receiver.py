#!/usr/bin/env python3
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

    last = None
    with open(outfile, "w") as f:
        f.write("delta_us\tpkt_len\n")
        try:
            while True:
                data, _ = sock.recvfrom(65535)
                now = time.monotonic_ns()
                if last is None:
                    delta_us = 0
                else:
                    delta_us = (now - last) // 1000
                last = now
                f.write(f"{delta_us}\t{len(data)}\n")
        except KeyboardInterrupt:
            pass
        finally:
            sock.close()

if __name__ == "__main__":
    main()