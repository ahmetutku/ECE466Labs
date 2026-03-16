#!/usr/bin/env python3
import csv
import signal
import socket
import subprocess
import sys
import threading
import time
from pathlib import Path


EXPERIMENTS = [(5, 1), (5, 5), (5, 9)]
LINK_BPS = 10_000_000
BUFFER_BYTES = 100_000
DRAIN_WAIT_S = 2.0


def read_trace(trace_path: Path):
    rows = []
    with trace_path.open() as f:
        for line in f:
            parts = line.split()
            if len(parts) < 3:
                continue
            rows.append((int(parts[0]), int(parts[1]), int(parts[2])))
    return rows


def average_rate_mbps(rows):
    total_bytes = sum(size for _, _, size in rows)
    span_s = (rows[-1][1] - rows[0][1]) / 1e6
    return (total_bytes * 8.0) / (span_s * 1e6)


def scaled_rows(rows, target_mbps: int):
    scale = average_rate_mbps(rows) / target_mbps
    first_ts = rows[0][1]
    return [
        (seq, round((ts_us - first_ts) * scale), size)
        for seq, ts_us, size in rows
    ]


def write_trace(rows, out_path: Path, duration_limit_us: int):
    with out_path.open("w") as f:
        for seq, ts_us, size in rows:
            if ts_us > duration_limit_us:
                break
            f.write(f"{seq} {ts_us} {size}\n")


def stop_process(proc: subprocess.Popen):
    proc.send_signal(signal.SIGINT)
    try:
        proc.wait(timeout=3)
    except subprocess.TimeoutExpired:
        proc.terminate()
        try:
            proc.wait(timeout=3)
        except subprocess.TimeoutExpired:
            proc.kill()
            proc.wait()


class SinkCollector(threading.Thread):
    def __init__(self, port: int):
        super().__init__(daemon=True)
        self.port = port
        self.stop_event = threading.Event()
        self.stats = {
            0x01: {"bytes": 0, "packets": 0},
            0x02: {"bytes": 0, "packets": 0},
        }
        self.first_ns = None
        self.last_ns = None

    def run(self):
        sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        sock.bind(("", self.port))
        sock.settimeout(0.5)
        try:
            while not self.stop_event.is_set():
                try:
                    packet, _ = sock.recvfrom(65535)
                except socket.timeout:
                    continue
                now = time.monotonic_ns()
                if self.first_ns is None:
                    self.first_ns = now
                self.last_ns = now
                if not packet:
                    continue
                tag = packet[0]
                if tag in self.stats:
                    self.stats[tag]["bytes"] += len(packet)
                    self.stats[tag]["packets"] += 1
        finally:
            sock.close()

    def stop(self):
        self.stop_event.set()
        self.join()

    def active_time_s(self):
        if self.first_ns is None or self.last_ns is None:
            return 0.0
        return (self.last_ns - self.first_ns) / 1e9


def throughput_mbps(bytes_sent: int, active_time_s: float):
    if active_time_s <= 0:
        return 0.0
    return (bytes_sent * 8.0) / (active_time_s * 1e6)


def main():
    part2_dir = Path(__file__).resolve().parent
    lab3_dir = part2_dir.parent
    poisson_trace = lab3_dir / "Part1" / "Part1a" / "poisson3.data"
    poisson_sender = part2_dir / "PoissonTaggedSender.py"
    rows = read_trace(poisson_trace)

    summary_rows = []
    summary_csv = part2_dir / "sp_starvation_summary.csv"

    for idx, (n1, n2) in enumerate(EXPERIMENTS, start=1):
        label = f"{n1}_{n2}"
        low_rows = scaled_rows(rows, n1)
        high_rows = scaled_rows(rows, n2)
        common_duration_us = min(low_rows[-1][1], high_rows[-1][1])

        low_trace = part2_dir / f"sp_low_{label}.data"
        high_trace = part2_dir / f"sp_high_{label}.data"
        scheduler_log = part2_dir / f"sp_scheduler_{label}.log"
        write_trace(low_rows, low_trace, common_duration_us)
        write_trace(high_rows, high_trace, common_duration_us)

        in_port = 9700 + idx
        out_port = 9800 + idx
        scheduler_cmd = [
            sys.executable,
            str(lab3_dir / "packet_scheduler.py"),
            str(in_port),
            "127.0.0.1",
            str(out_port),
            str(LINK_BPS),
            str(BUFFER_BYTES),
            str(BUFFER_BYTES),
            "--max-packet-size",
            "1480",
            "--logfile",
            str(part2_dir / f"sp_sched_eval_{label}.csv"),
        ]
        low_cmd = [
            sys.executable,
            str(poisson_sender),
            "127.0.0.1",
            str(in_port),
            str(low_trace),
            "--tag-byte",
            "0x01",
        ]
        high_cmd = [
            sys.executable,
            str(poisson_sender),
            "127.0.0.1",
            str(in_port),
            str(high_trace),
            "--tag-byte",
            "0x02",
        ]

        print(f"\n=== SP starvation experiment (N1, N2)=({n1}, {n2}) Mbps ===")
        print("$", " ".join(str(part) for part in scheduler_cmd))
        print("$", " ".join(str(part) for part in low_cmd))
        print("$", " ".join(str(part) for part in high_cmd))

        sink = SinkCollector(out_port)
        sink.start()
        with scheduler_log.open("w") as log_file:
            scheduler_proc = subprocess.Popen(
                scheduler_cmd,
                cwd=lab3_dir,
                stdout=log_file,
                stderr=subprocess.STDOUT,
            )
            try:
                time.sleep(1.0)
                low_proc = subprocess.Popen(low_cmd, cwd=lab3_dir)
                high_proc = subprocess.Popen(high_cmd, cwd=lab3_dir)
                low_proc.wait()
                high_proc.wait()
                time.sleep(DRAIN_WAIT_S)
            finally:
                stop_process(scheduler_proc)
                sink.stop()

        active_time_s = sink.active_time_s()
        low_tp = throughput_mbps(sink.stats[0x01]["bytes"], active_time_s)
        high_tp = throughput_mbps(sink.stats[0x02]["bytes"], active_time_s)
        total_tp = low_tp + high_tp
        summary_rows.append({
            "N1_Mbps": n1,
            "N2_Mbps": n2,
            "measured_low_throughput_Mbps": low_tp,
            "measured_high_throughput_Mbps": high_tp,
            "total_output_Mbps": total_tp,
            "sink_active_time_s": active_time_s,
        })

    with summary_csv.open("w", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=list(summary_rows[0].keys()))
        writer.writeheader()
        writer.writerows(summary_rows)

    print("\nSummary CSV:")
    print(summary_csv.name)
    print("\nFinal table:")
    print(
        "N1_Mbps  N2_Mbps  measured_low_throughput_Mbps  "
        "measured_high_throughput_Mbps  total_output_Mbps  sink_active_time_s"
    )
    for row in summary_rows:
        print(
            f"{row['N1_Mbps']:>7}  {row['N2_Mbps']:>7}  "
            f"{row['measured_low_throughput_Mbps']:.6f}                    "
            f"{row['measured_high_throughput_Mbps']:.6f}                     "
            f"{row['total_output_Mbps']:.6f}         {row['sink_active_time_s']:.6f}"
        )


if __name__ == "__main__":
    main()
