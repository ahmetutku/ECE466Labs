#!/usr/bin/env python3
import csv
import signal
import subprocess
import sys
import time
from pathlib import Path

import matplotlib.pyplot as plt


LOADS_MBPS = [1, 5, 9]
FIFO_LINK_BPS = 10_000_000


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


def write_scaled_trace(rows, target_mbps: int, out_path: Path):
    base_rate = average_rate_mbps(rows)
    scale = base_rate / target_mbps
    first_ts = rows[0][1]
    with out_path.open("w") as f:
        for seq, ts_us, size in rows:
            shifted_us = ts_us - first_ts
            scaled_us = round(shifted_us * scale)
            f.write(f"{seq} {scaled_us} {size}\n")


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


def plot_csv(csv_path: Path, label: str, out_dir: Path):
    arrival_times = []
    backlogs = []
    waiting_times_t = []
    waiting_times = []
    drop_times = []
    cum_drops = []

    with csv_path.open() as f:
        reader = csv.DictReader(f)
        for row in reader:
            arrival_t = float(row["arrival_time_s"])
            arrival_times.append(arrival_t)
            backlogs.append(int(row["backlog_bytes"]))
            drop_times.append(arrival_t)
            cum_drops.append(int(row["cum_drops"]))
            if row["dropped"] == "0" and row["waiting_time_s"] != "":
                waiting_times_t.append(arrival_t)
                waiting_times.append(float(row["waiting_time_s"]))

    plots = []
    backlog_plot = out_dir / f"fifo_backlog_{label}.png"
    plt.figure(figsize=(8, 4))
    plt.plot(arrival_times, backlogs, linewidth=1.0)
    plt.xlabel("Arrival time (s)")
    plt.ylabel("Backlog (bytes)")
    plt.title(f"FIFO backlog vs time ({label})")
    plt.tight_layout()
    plt.savefig(backlog_plot)
    plt.close()
    plots.append(backlog_plot.name)

    wait_plot = out_dir / f"fifo_waiting_{label}.png"
    plt.figure(figsize=(8, 4))
    plt.plot(waiting_times_t, waiting_times, linewidth=1.0)
    plt.xlabel("Arrival time (s)")
    plt.ylabel("Waiting time (s)")
    plt.title(f"FIFO waiting time vs time ({label})")
    plt.tight_layout()
    plt.savefig(wait_plot)
    plt.close()
    plots.append(wait_plot.name)

    drops_plot = out_dir / f"fifo_drops_{label}.png"
    plt.figure(figsize=(8, 4))
    plt.step(drop_times, cum_drops, where="post")
    plt.xlabel("Arrival time (s)")
    plt.ylabel("Cumulative drops")
    plt.title(f"FIFO cumulative drops vs time ({label})")
    plt.tight_layout()
    plt.savefig(drops_plot)
    plt.close()
    plots.append(drops_plot.name)

    return plots


def summarize_csv(csv_path: Path):
    rows = 0
    drops = 0
    max_backlog = 0
    max_wait = 0.0
    with csv_path.open() as f:
        reader = csv.DictReader(f)
        for row in reader:
            rows += 1
            drops = max(drops, int(row["cum_drops"]))
            max_backlog = max(max_backlog, int(row["backlog_bytes"]))
            if row["waiting_time_s"]:
                max_wait = max(max_wait, float(row["waiting_time_s"]))
    return rows, drops, max_backlog, max_wait


def main():
    lab_dir = Path(__file__).resolve().parent
    trace_path = lab_dir / "Part1" / "Part1a" / "poisson3.data"
    sender_path = lab_dir / "Part1" / "Part1a" / "Sender.py"
    rows = read_trace(trace_path)

    generated_csvs = []
    generated_plots = []

    for load in LOADS_MBPS:
        label = f"{load}mbps"
        scaled_trace = lab_dir / f"poisson3_{label}.data"
        csv_path = lab_dir / f"fifo_eval_{label}.csv"
        write_scaled_trace(rows, load, scaled_trace)

        in_port = 9100 + load
        out_port = 9200 + load
        scheduler_cmd = [
            sys.executable,
            "packet_scheduler.py",
            str(in_port),
            "127.0.0.1",
            str(out_port),
            str(FIFO_LINK_BPS),
            "100000",
            "--max-packet-size",
            "1480",
            "--logfile",
            csv_path.name,
        ]
        sender_cmd = [
            sys.executable,
            str(sender_path),
            "127.0.0.1",
            str(in_port),
            str(scaled_trace),
        ]

        print(f"\n=== Running FIFO evaluation at {load} Mbps ===")
        print("$", " ".join(str(part) for part in scheduler_cmd))
        scheduler_proc = subprocess.Popen(scheduler_cmd, cwd=lab_dir)
        try:
            time.sleep(1.0)
            run_command(sender_cmd, lab_dir)
            time.sleep(2.0)
        finally:
            stop_process(scheduler_proc)

        generated_csvs.append(csv_path.name)
        generated_plots.extend(plot_csv(csv_path, label, lab_dir))
        rows_logged, drops, max_backlog, max_wait = summarize_csv(csv_path)
        print(
            f"Saved {csv_path.name}: rows={rows_logged}, drops={drops}, "
            f"max_backlog={max_backlog}, max_wait={max_wait:.6f}s"
        )

    print("\nGenerated CSV files:")
    for name in generated_csvs:
        print(name)

    print("\nGenerated plot files:")
    for name in generated_plots:
        print(name)


if __name__ == "__main__":
    main()
