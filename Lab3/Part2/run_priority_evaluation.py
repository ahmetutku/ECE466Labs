#!/usr/bin/env python3
import csv
import os
import signal
import subprocess
import sys
import time
from pathlib import Path

import matplotlib.pyplot as plt


LOADS_MBPS = [1, 5, 9]
LINK_BPS = 20_000_000
BUFFER_BYTES = 100_000
DRAIN_WAIT_S = 5.0
EXPERIMENT_DURATION_S = 60
VIDEO_FRAME_RATE = 30


def read_poisson_trace(trace_path: Path):
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


def write_scaled_poisson(rows, target_mbps: int, out_path: Path, duration_limit_s: int):
    scale = average_rate_mbps(rows) / target_mbps
    first_ts = rows[0][1]
    with out_path.open("w") as f:
        for seq, ts_us, size in rows:
            scaled_us = round((ts_us - first_ts) * scale)
            if scaled_us > duration_limit_s * 1_000_000:
                break
            f.write(f"{seq} {scaled_us} {size}\n")


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


def split_by_class(combined_csv: Path, high_csv: Path, low_csv: Path):
    csv.field_size_limit(sys.maxsize)
    with combined_csv.open() as f:
        clean_lines = (
            line.replace("\x00", "")
            for line in f
            if line.strip("\x00\r\n")
        )
        rows = list(csv.DictReader(clean_lines))

    fieldnames = list(rows[0].keys()) if rows else [
        "arrival_time_s",
        "packet_size_bytes",
        "priority_class",
        "source_tag_hex",
        "backlog_bytes",
        "departure_time_s",
        "waiting_time_s",
        "dropped",
        "cum_drops",
        "cum_drops_class",
    ]
    grouped = {"high": [], "low": []}
    for row in rows:
        priority_class = row["priority_class"]
        if priority_class in grouped:
            grouped[priority_class].append(row)

    for path, cls in [(high_csv, "high"), (low_csv, "low")]:
        with path.open("w", newline="") as f:
            writer = csv.DictWriter(f, fieldnames=fieldnames)
            writer.writeheader()
            writer.writerows(grouped[cls])

    return grouped


def plot_load(label: str, grouped_rows: dict[str, list[dict]], out_dir: Path):
    plots = []

    plt.figure(figsize=(9, 4))
    for cls, color in [("high", "tab:red"), ("low", "tab:blue")]:
        rows = grouped_rows[cls]
        t = [float(r["arrival_time_s"]) for r in rows]
        b = [int(r["backlog_bytes"]) for r in rows]
        plt.plot(t, b, label=cls, linewidth=1.0, color=color)
    plt.xlabel("Arrival time (s)")
    plt.ylabel("Backlog (bytes)")
    plt.title(f"Priority backlog vs time ({label})")
    plt.legend()
    plt.tight_layout()
    backlog_plot = out_dir / f"priority_backlog_{label}.png"
    plt.savefig(backlog_plot)
    plt.close()
    plots.append(backlog_plot.name)

    plt.figure(figsize=(9, 4))
    for cls, color in [("high", "tab:red"), ("low", "tab:blue")]:
        rows = grouped_rows[cls]
        t = [float(r["arrival_time_s"]) for r in rows if r["waiting_time_s"]]
        w = [float(r["waiting_time_s"]) for r in rows if r["waiting_time_s"]]
        plt.plot(t, w, label=cls, linewidth=1.0, color=color)
    plt.xlabel("Arrival time (s)")
    plt.ylabel("Waiting time (s)")
    plt.title(f"Priority waiting time vs time ({label})")
    plt.legend()
    plt.tight_layout()
    wait_plot = out_dir / f"priority_waiting_{label}.png"
    plt.savefig(wait_plot)
    plt.close()
    plots.append(wait_plot.name)

    plt.figure(figsize=(9, 4))
    for cls, color in [("high", "tab:red"), ("low", "tab:blue")]:
        rows = grouped_rows[cls]
        t = [float(r["arrival_time_s"]) for r in rows]
        d = [int(r["cum_drops_class"]) for r in rows]
        plt.step(t, d, where="post", label=cls, color=color)
    plt.xlabel("Arrival time (s)")
    plt.ylabel("Cumulative drops")
    plt.title(f"Priority cumulative drops vs time ({label})")
    plt.legend()
    plt.tight_layout()
    drop_plot = out_dir / f"priority_drops_{label}.png"
    plt.savefig(drop_plot)
    plt.close()
    plots.append(drop_plot.name)

    return plots


def summarize_rows(rows: list[dict]):
    if not rows:
        return {"max_backlog": 0, "max_wait": 0.0, "drops": 0}
    max_backlog = max(int(r["backlog_bytes"]) for r in rows)
    max_wait = max((float(r["waiting_time_s"]) for r in rows if r["waiting_time_s"]), default=0.0)
    drops = max(int(r["cum_drops_class"]) for r in rows)
    return {"max_backlog": max_backlog, "max_wait": max_wait, "drops": drops}


def fifo_summary(load: int):
    fifo_csv = Path(__file__).resolve().parents[1] / "Part1" / "part1bc" / f"fifo_eval_{load}mbps.csv"
    if not fifo_csv.exists():
        return None
    with fifo_csv.open() as f:
        rows = list(csv.DictReader(f))
    if not rows:
        return None
    return {
        "max_backlog": max(int(r["backlog_bytes"]) for r in rows),
        "max_wait": max((float(r["waiting_time_s"]) for r in rows if r["waiting_time_s"]), default=0.0),
        "drops": max(int(r["cum_drops"]) for r in rows),
    }


def main():
    part2_dir = Path(__file__).resolve().parent
    lab3_dir = part2_dir.parent
    poisson_trace = lab3_dir / "Part1" / "Part1a" / "poisson3.data"
    video_trace = part2_dir.parent.parent / "Lab2" / "part1" / "movietrace.data"
    poisson_sender = part2_dir / "PoissonTaggedSender.py"
    video_sender = part2_dir / "VideoTaggedSender.py"
    poisson_rows = read_poisson_trace(poisson_trace)

    generated_csvs = []
    generated_plots = []
    summaries = []

    for load in LOADS_MBPS:
        label = f"{load}mbps"
        scaled_trace = part2_dir / f"poisson3_priority_{label}.data"
        combined_csv = part2_dir / f"priority_eval_{label}_combined.csv"
        high_csv = part2_dir / f"priority_eval_{label}_high.csv"
        low_csv = part2_dir / f"priority_eval_{label}_low.csv"
        scheduler_log = part2_dir / f"priority_scheduler_{label}.log"

        write_scaled_poisson(
            poisson_rows, load, scaled_trace, duration_limit_s=EXPERIMENT_DURATION_S
        )

        in_port = 9500 + load
        out_port = 9600 + load
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
            str(combined_csv),
        ]
        poisson_cmd = [
            sys.executable,
            str(poisson_sender),
            "127.0.0.1",
            str(in_port),
            str(scaled_trace),
        ]
        video_cmd = [
            sys.executable,
            str(video_sender),
            "127.0.0.1",
            str(in_port),
            str(video_trace),
            "--limit",
            str(EXPERIMENT_DURATION_S * VIDEO_FRAME_RATE),
        ]

        print(f"\n=== Priority evaluation at Poisson load {load} Mbps ===")
        print("$", " ".join(str(part) for part in scheduler_cmd))
        print("$", " ".join(str(part) for part in poisson_cmd))
        print("$", " ".join(str(part) for part in video_cmd))
        with scheduler_log.open("w") as log_file:
            scheduler_proc = subprocess.Popen(
                scheduler_cmd,
                cwd=lab3_dir,
                stdout=log_file,
                stderr=subprocess.STDOUT,
                env={**os.environ, "PYTHONUNBUFFERED": "1"},
            )
            try:
                time.sleep(1.0)
                poisson_proc = subprocess.Popen(poisson_cmd, cwd=lab3_dir)
                video_proc = subprocess.Popen(video_cmd, cwd=lab3_dir)
                poisson_proc.wait()
                video_proc.wait()
                time.sleep(DRAIN_WAIT_S)
            finally:
                stop_process(scheduler_proc)

        grouped = split_by_class(combined_csv, high_csv, low_csv)
        generated_csvs.extend([combined_csv.name, high_csv.name, low_csv.name])
        generated_plots.extend(plot_load(label, grouped, part2_dir))

        high_summary = summarize_rows(grouped["high"])
        low_summary = summarize_rows(grouped["low"])
        fifo = fifo_summary(load)
        summaries.append((load, high_summary, low_summary, fifo))
        print(
            f"high: max_backlog={high_summary['max_backlog']} bytes, "
            f"max_wait={high_summary['max_wait']:.6f}s, drops={high_summary['drops']}"
        )
        print(
            f"low:  max_backlog={low_summary['max_backlog']} bytes, "
            f"max_wait={low_summary['max_wait']:.6f}s, drops={low_summary['drops']}"
        )

    print("\nGenerated CSV files:")
    for name in generated_csvs:
        print(name)

    print("\nGenerated plot files:")
    for name in generated_plots:
        print(name)

    print("\nComparison vs Exercise 1-c FIFO:")
    for load, high_summary, low_summary, fifo in summaries:
        if fifo is None:
            print(f"{load} Mbps: FIFO baseline not found")
            continue
        print(
            f"{load} Mbps: FIFO max_backlog={fifo['max_backlog']} bytes, "
            f"max_wait={fifo['max_wait']:.6f}s, drops={fifo['drops']} | "
            f"Priority high backlog={high_summary['max_backlog']}, wait={high_summary['max_wait']:.6f}s, drops={high_summary['drops']} | "
            f"Priority low backlog={low_summary['max_backlog']}, wait={low_summary['max_wait']:.6f}s, drops={low_summary['drops']}"
        )


if __name__ == "__main__":
    main()
