#!/usr/bin/env python3
import csv
import os
import socket
import sys
import time

def main():
    if len(sys.argv) not in (2, 3):
        print(f"Usage: {sys.argv[0]} <listen_port> [outfile]")
        sys.exit(1)

    listen_port = int(sys.argv[1])
    script_dir = os.path.dirname(os.path.abspath(__file__))
    outfile = os.path.join(script_dir, "receiver_log.csv")

    # Preserve prior CLI shape while enforcing the required fixed CSV filename.
    if len(sys.argv) == 3:
        print(f"Ignoring outfile argument '{sys.argv[2]}'; writing to {outfile}")

    sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    sock.bind(("", listen_port))
    print(f"Waiting for UDP on port {listen_port} ... (Ctrl+C to stop)")
    print(f"Logging packet records to {outfile}")

    start_time = time.time()
    last_report_time = start_time
    cumulative_bytes = 0
    cumulative_packets = 0

    with open(outfile, "w", newline="") as csv_file:
        writer = csv.writer(csv_file)
        writer.writerow([
            "time_s",
            "packet_size_bytes",
            "cumulative_bytes",
            "cumulative_packets",
        ])
        csv_file.flush()

        def print_summary(now):
            elapsed = now - start_time
            avg_mbps = (cumulative_bytes * 8.0) / (elapsed * 1e6) if elapsed > 0 else 0.0
            print(
                f"[{elapsed:8.3f}s] packets={cumulative_packets} "
                f"bytes={cumulative_bytes} avg_throughput={avg_mbps:.3f} Mbps"
            )

        try:
            while True:
                data, _ = sock.recvfrom(65535)
                now = time.time()
                packet_size = len(data)
                cumulative_bytes += packet_size
                cumulative_packets += 1

                writer.writerow([now, packet_size, cumulative_bytes, cumulative_packets])
                csv_file.flush()

                if now - last_report_time >= 1.0:
                    print_summary(now)
                    last_report_time = now
        except KeyboardInterrupt:
            print("\nStopping receiver (Ctrl+C).")
        finally:
            final_time = time.time()
            print_summary(final_time)
            print(
                f"Final totals: packets={cumulative_packets}, "
                f"bytes={cumulative_bytes}, elapsed={final_time - start_time:.3f}s"
            )
            sock.close()

if __name__ == "__main__":
    main()