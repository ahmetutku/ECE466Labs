#!/usr/bin/env python3
import csv
import signal
import socket
import subprocess
import sys
import threading
import time
from pathlib import Path


EXPERIMENTS = [(5, 1), (5, 5), (5, 10)]
LINK_MBPS = 1
LINK_BPS = LINK_MBPS * 1_000_000
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


def run_command(cmd, cwd: Path):
    print("$", " ".join(str(part) for part in cmd))
    return subprocess.run(cmd, cwd=cwd, check=True)


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
            1: {"bytes": 0, "packets": 0},
            2: {"bytes": 0, "packets": 0},
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
                source_id = packet[0]
                if source_id not in self.stats:
                    continue
                self.stats[source_id]["bytes"] += len(packet)
                self.stats[source_id]["packets"] += 1
        finally:
            sock.close()

    def stop(self):
        self.stop_event.set()
        self.join()

    def active_time_s(self):
        if self.first_ns is None or self.last_ns is None:
            return 0.0
        return (self.last_ns - self.first_ns) / 1e9


def measured_throughput_mbps(bytes_received: int, active_time_s: float):
    if active_time_s <= 0:
        return 0.0
    return (bytes_received * 8.0) / (active_time_s * 1e6)


def main():
    part1d_dir = Path(__file__).resolve().parent
    lab3_dir = part1d_dir.parents[1]
    sender_path = lab3_dir / "Part1" / "Part1a" / "Sender.py"
    trace_path = lab3_dir / "Part1" / "Part1a" / "poisson3.data"
    rows = read_trace(trace_path)

    summary_rows = []
    summary_csv = part1d_dir / "fifo_source_summary.csv"

    for idx, (n1, n2) in enumerate(EXPERIMENTS, start=1):
        label = f"{n1}_{n2}"
        trace1_rows = scaled_rows(rows, n1)
        trace2_rows = scaled_rows(rows, n2)
        common_duration_us = min(trace1_rows[-1][1], trace2_rows[-1][1])

        trace1_path = part1d_dir / f"poisson3_src1_{label}.data"
        trace2_path = part1d_dir / f"poisson3_src2_{label}.data"
        sched_log = part1d_dir / f"fifo_source_sched_{label}.csv"
        write_trace(trace1_rows, trace1_path, common_duration_us)
        write_trace(trace2_rows, trace2_path, common_duration_us)

        in_port = 9300 + idx
        out_port = 9400 + idx
        scheduler_cmd = [
            sys.executable,
            str(lab3_dir / "packet_scheduler.py"),
            str(in_port),
            "127.0.0.1",
            str(out_port),
            str(LINK_BPS),
            str(BUFFER_BYTES),
            "--max-packet-size",
            "1480",
            "--logfile",
            str(sched_log),
        ]
        sender1_cmd = [
            sys.executable,
            str(sender_path),
            "127.0.0.1",
            str(in_port),
            str(trace1_path),
            "--source-id",
            "1",
        ]
        sender2_cmd = [
            sys.executable,
            str(sender_path),
            "127.0.0.1",
            str(in_port),
            str(trace2_path),
            "--source-id",
            "2",
        ]

        print(f"\n=== FIFO source experiment (N1, N2)=({n1}, {n2}) Mbps ===")
        print("$", " ".join(str(part) for part in scheduler_cmd))
        sink = SinkCollector(out_port)
        sink.start()
        scheduler_proc = subprocess.Popen(scheduler_cmd, cwd=lab3_dir)
        try:
            time.sleep(1.0)
            sender1 = subprocess.Popen(sender1_cmd, cwd=lab3_dir)
            sender2 = subprocess.Popen(sender2_cmd, cwd=lab3_dir)
            print("$", " ".join(str(part) for part in sender1_cmd))
            print("$", " ".join(str(part) for part in sender2_cmd))
            sender1.wait()
            sender2.wait()
            time.sleep(DRAIN_WAIT_S)
        finally:
            stop_process(scheduler_proc)
            sink.stop()

        active_time_s = sink.active_time_s()
        measured_t1 = measured_throughput_mbps(sink.stats[1]["bytes"], active_time_s)
        measured_t2 = measured_throughput_mbps(sink.stats[2]["bytes"], active_time_s)
        predicted_t1 = LINK_MBPS * n1 / (n1 + n2)
        predicted_t2 = LINK_MBPS * n2 / (n1 + n2)
        error_t1 = abs(measured_t1 - predicted_t1) / predicted_t1 * 100.0
        error_t2 = abs(measured_t2 - predicted_t2) / predicted_t2 * 100.0

        summary_rows.append({
            "N1_Mbps": n1,
            "N2_Mbps": n2,
            "measured_T1_Mbps": measured_t1,
            "predicted_T1_Mbps": predicted_t1,
            "error_T1_pct": error_t1,
            "measured_T2_Mbps": measured_t2,
            "predicted_T2_Mbps": predicted_t2,
            "error_T2_pct": error_t2,
            "sink_active_time_s": active_time_s,
        })

        print(
            f"Measured: T1={measured_t1:.4f} Mbps, T2={measured_t2:.4f} Mbps | "
            f"Predicted: T1={predicted_t1:.4f}, T2={predicted_t2:.4f}"
        )

    with summary_csv.open("w", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=list(summary_rows[0].keys()))
        writer.writeheader()
        writer.writerows(summary_rows)

    print("\nSummary CSV:")
    print(summary_csv.name)

    print("\nSummary table:")
    print("N1  N2  Measured T1  Predicted T1  Error T1%  Measured T2  Predicted T2  Error T2%")
    for row in summary_rows:
        print(
            f"{row['N1_Mbps']:>2}  {row['N2_Mbps']:>2}  "
            f"{row['measured_T1_Mbps']:.4f}       {row['predicted_T1_Mbps']:.4f}        "
            f"{row['error_T1_pct']:.2f}      {row['measured_T2_Mbps']:.4f}       "
            f"{row['predicted_T2_Mbps']:.4f}        {row['error_T2_pct']:.2f}"
        )


if __name__ == "__main__":
    main()
