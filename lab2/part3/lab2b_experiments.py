#!/usr/bin/env python3
import argparse
import os
import signal
import subprocess
import time
from dataclasses import dataclass

import matplotlib.pyplot as plt
import numpy as np


ROOT_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
PART2_DIR = os.path.join(ROOT_DIR, "part2")
PART3_DIR = os.path.join(ROOT_DIR, "part3")
PLOTS_DIR = os.path.join(ROOT_DIR, "plots")

SENDER_PY = os.path.join(PART2_DIR, "Sender.py")
RECEIVER_PY = os.path.join(PART2_DIR, "Receiver.py")
TOKEN_BUCKET_PY = os.path.join(PART3_DIR, "token_bucket.py")


@dataclass
class Scenario:
    tag: str
    n: int
    l_bytes: int
    t_ms: float


SCENARIOS = [
    Scenario("s1", 1, 1250, 1.0),
    Scenario("s2", 10, 1250, 10.0),
    Scenario("s3", 4, 625, 20.0),
]


def ensure_dirs():
    os.makedirs(PLOTS_DIR, exist_ok=True)


def kill_process(proc):
    if proc is None or proc.poll() is not None:
        return
    proc.terminate()
    try:
        proc.wait(timeout=2.0)
    except subprocess.TimeoutExpired:
        proc.kill()
        proc.wait(timeout=2.0)


def run_cmd(cmd, cwd=None):
    return subprocess.Popen(cmd, cwd=cwd)


def read_gen_log(path):
    deltas_ms = []
    sizes = []
    with open(path, "r") as f:
        header = True
        for line in f:
            line = line.strip()
            if not line:
                continue
            if header:
                header = False
                continue
            seq, d_ms, sz = line.split()
            _ = int(seq)
            deltas_ms.append(float(d_ms))
            sizes.append(float(sz))
    return np.array(deltas_ms), np.array(sizes)


def read_sink_log(path):
    deltas_us = []
    sizes = []
    with open(path, "r") as f:
        header = True
        for line in f:
            line = line.strip()
            if not line:
                continue
            if header and ("delta" in line or "elapsed" in line):
                header = False
                continue
            header = False
            du, sz = line.split()
            deltas_us.append(float(du))
            sizes.append(float(sz))
    return np.array(deltas_us), np.array(sizes)


def read_tb_log(path):
    deltas_us = []
    sizes = []
    backlog = []
    tokens = []
    with open(path, "r") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            du, sz, b, tok = line.split()
            deltas_us.append(float(du))
            sizes.append(float(sz))
            backlog.append(float(b))
            tokens.append(float(tok))
    return np.array(deltas_us), np.array(sizes), np.array(tokens), np.array(backlog)


def cumsum_time_s_from_ms(d_ms):
    return np.cumsum(d_ms) / 1000.0


def cumsum_time_s_from_us(d_us):
    return np.cumsum(d_us) / 1e6


def pick_scale(max_value):
    if max_value > 1_000_000:
        return 1_000_000.0, "M"
    if max_value > 1_000:
        return 1_000.0, "K"
    return 1.0, ""


def plot_cumulative(series, title, out_name, base_unit="Bytes"):
    max_value = 0.0
    for _, _, y in series:
        if len(y) > 0:
            max_value = max(max_value, float(np.max(y)))

    scale, prefix = pick_scale(max_value)

    plt.figure(figsize=(8, 4.5))
    for label, t, y in series:
        plt.plot(t, y / scale, label=label)
    plt.xlabel("Time (s)")
    plt.ylabel(f"Cumulative ({prefix}{base_unit})")
    plt.title(title)
    plt.legend()
    plt.tight_layout()
    plt.savefig(os.path.join(PLOTS_DIR, out_name), dpi=200)
    plt.close()


def plot_tb_backlog(tb_t, tb_tokens, tb_backlog, title, out_name, base_unit="Bytes"):
    max_value = 0.0
    if len(tb_tokens) > 0:
        max_value = max(max_value, float(np.max(tb_tokens)))
    if len(tb_backlog) > 0:
        max_value = max(max_value, float(np.max(tb_backlog)))
    scale, prefix = pick_scale(max_value)

    plt.figure(figsize=(8, 4.5))
    plt.plot(tb_t, tb_tokens / scale, label="TB(t)")
    plt.plot(tb_t, tb_backlog / scale, label="Backlog B(t)")
    plt.xlabel("Time (s)")
    plt.ylabel(f"{prefix}{base_unit}")
    plt.title(title)
    plt.legend()
    plt.tight_layout()
    plt.savefig(os.path.join(PLOTS_DIR, out_name), dpi=200)
    plt.close()


def run_sender_periodic(dst_port, scenario, gen_log, packet_count=500):
    cmd = [
        "python3", SENDER_PY,
        "127.0.0.1", str(dst_port),
        "--periodic", str(scenario.n), str(scenario.l_bytes), str(scenario.t_ms),
        "--count", str(packet_count),
        "--gen-log", gen_log,
    ]
    proc = run_cmd(cmd, cwd=PART2_DIR)
    proc.wait(timeout=120)


def run_exercise_1a_scenario(scenario, packet_count=500):
    sink_port = 52000

    gen_log = os.path.join(PART3_DIR, f"1a_{scenario.tag}_generator.log")
    sink_log = os.path.join(PART3_DIR, f"1a_{scenario.tag}_sink.log")

    sink_proc = None
    try:
        sink_proc = run_cmd(["python3", RECEIVER_PY, str(sink_port), sink_log], cwd=PART2_DIR)
        time.sleep(0.2)

        run_sender_periodic(sink_port, scenario, gen_log, packet_count=packet_count)
        time.sleep(0.5)
    finally:
        kill_process(sink_proc)

    gen_d_ms, gen_sz = read_gen_log(gen_log)
    sink_d_us, sink_sz = read_sink_log(sink_log)

    gen_t = cumsum_time_s_from_ms(gen_d_ms)
    sink_t = cumsum_time_s_from_us(sink_d_us)

    plot_cumulative(
        series=[
            ("Generator cumulative", gen_t, np.cumsum(gen_sz)),
            ("Sink cumulative", sink_t, np.cumsum(sink_sz)),
        ],
        title=f"Exercise 1-a ({scenario.tag.upper()})",
        out_name=f"1a_{scenario.tag}_cumulative.png",
        base_unit="Bytes",
    )


def run_exercise_2b_scenario(scenario, packet_count=500, bucket_rate_bytes_per_sec=1_250_000, bucket_size_bytes=1250):
    in_port = 53000
    sink_port = 53001

    gen_log = os.path.join(PART3_DIR, f"2b_{scenario.tag}_generator.log")
    sink_log = os.path.join(PART3_DIR, f"2b_{scenario.tag}_sink.log")
    tb_log = os.path.join(PART3_DIR, f"2b_{scenario.tag}_tb.log")

    sink_proc = None
    tb_proc = None
    try:
        sink_proc = run_cmd(["python3", RECEIVER_PY, str(sink_port), sink_log], cwd=PART2_DIR)
        time.sleep(0.2)

        tb_proc = run_cmd([
            "python3", TOKEN_BUCKET_PY,
            str(in_port), "127.0.0.1", str(sink_port),
            str(bucket_size_bytes), str(bucket_rate_bytes_per_sec),
            "--max-packet-size", "1250",
            "--logfile", tb_log,
        ], cwd=PART3_DIR)
        time.sleep(0.2)

        run_sender_periodic(in_port, scenario, gen_log, packet_count=packet_count)
        time.sleep(0.8)
    finally:
        kill_process(tb_proc)
        kill_process(sink_proc)

    gen_d_ms, gen_sz = read_gen_log(gen_log)
    sink_d_us, sink_sz = read_sink_log(sink_log)
    tb_d_us, tb_sz, tb_tokens, tb_backlog = read_tb_log(tb_log)

    gen_t = cumsum_time_s_from_ms(gen_d_ms)
    sink_t = cumsum_time_s_from_us(sink_d_us)
    tb_t = cumsum_time_s_from_us(tb_d_us)

    plot_cumulative(
        series=[
            ("Generator", gen_t, np.cumsum(gen_sz)),
            ("Token bucket arrivals", tb_t, np.cumsum(tb_sz)),
            ("Sink", sink_t, np.cumsum(sink_sz)),
        ],
        title=f"Exercise 2-b cumulative ({scenario.tag.upper()})",
        out_name=f"2b_{scenario.tag}_cumulative.png",
        base_unit="Bytes",
    )

    plot_tb_backlog(
        tb_t=tb_t,
        tb_tokens=tb_tokens,
        tb_backlog=tb_backlog,
        title=f"Exercise 2-b TB/Backlog ({scenario.tag.upper()})",
        out_name=f"2b_{scenario.tag}_tb_backlog.png",
        base_unit="Bytes",
    )


def offered_rate_mbps(scenario):
    return (scenario.n * scenario.l_bytes * 8.0 * (1000.0 / scenario.t_ms)) / 1_000_000.0


def scenario_for_rate_mbps(base_l_bytes, target_mbps):
    # N=1, L fixed, solve T_ms from target rate in Mbps
    # target_bps = L*8*1000 / T_ms
    target_bps = target_mbps * 1_000_000.0
    t_ms = (base_l_bytes * 8.0 * 1000.0) / target_bps
    return Scenario("max_rate", 1, base_l_bytes, t_ms)


def is_backlog_bounded(tb_backlog):
    if len(tb_backlog) < 20:
        return True
    second_half = tb_backlog[len(tb_backlog) // 2 :]
    span = float(np.max(second_half) - np.min(second_half))
    tail = second_half[-1]
    return span < 2_500.0 and tail < 2_500.0


def determine_max_supported_rate(bucket_rate_mbps=10.0):
    candidate_rates = np.arange(2.0, 20.5, 0.5)
    best_rate = candidate_rates[0]

    for rate in candidate_rates:
        scenario = scenario_for_rate_mbps(base_l_bytes=1250, target_mbps=float(rate))
        in_port = 54000
        sink_port = 54001

        gen_log = os.path.join(PART3_DIR, "2c_probe_generator.log")
        sink_log = os.path.join(PART3_DIR, "2c_probe_sink.log")
        tb_log = os.path.join(PART3_DIR, "2c_probe_tb.log")

        sink_proc = None
        tb_proc = None
        try:
            sink_proc = run_cmd(["python3", RECEIVER_PY, str(sink_port), sink_log], cwd=PART2_DIR)
            time.sleep(0.15)
            tb_proc = run_cmd([
                "python3", TOKEN_BUCKET_PY,
                str(in_port), "127.0.0.1", str(sink_port),
                "1250", str(int(bucket_rate_mbps * 1_000_000 / 8.0)),
                "--max-packet-size", "1250",
                "--logfile", tb_log,
            ], cwd=PART3_DIR)
            time.sleep(0.15)
            run_sender_periodic(in_port, scenario, gen_log, packet_count=500)
            time.sleep(0.5)
        finally:
            kill_process(tb_proc)
            kill_process(sink_proc)

        _, _, _, backlog = read_tb_log(tb_log)
        if is_backlog_bounded(backlog):
            best_rate = float(rate)
        else:
            break

    return best_rate


def run_exercise_2c(bucket_rate_mbps=10.0):
    max_rate = determine_max_supported_rate(bucket_rate_mbps=bucket_rate_mbps)
    scenario = scenario_for_rate_mbps(base_l_bytes=1250, target_mbps=max_rate)

    in_port = 55000
    sink_port = 55001

    gen_log = os.path.join(PART3_DIR, "2c_max_generator.log")
    sink_log = os.path.join(PART3_DIR, "2c_max_sink.log")
    tb_log = os.path.join(PART3_DIR, "2c_max_tb.log")

    sink_proc = None
    tb_proc = None
    try:
        sink_proc = run_cmd(["python3", RECEIVER_PY, str(sink_port), sink_log], cwd=PART2_DIR)
        time.sleep(0.2)
        tb_proc = run_cmd([
            "python3", TOKEN_BUCKET_PY,
            str(in_port), "127.0.0.1", str(sink_port),
            "1250", str(int(bucket_rate_mbps * 1_000_000 / 8.0)),
            "--max-packet-size", "1250",
            "--logfile", tb_log,
        ], cwd=PART3_DIR)
        time.sleep(0.2)

        run_sender_periodic(in_port, scenario, gen_log, packet_count=500)
        time.sleep(0.8)
    finally:
        kill_process(tb_proc)
        kill_process(sink_proc)

    gen_d_ms, gen_sz = read_gen_log(gen_log)
    sink_d_us, sink_sz = read_sink_log(sink_log)
    tb_d_us, tb_sz, tb_tokens, tb_backlog = read_tb_log(tb_log)

    gen_t = cumsum_time_s_from_ms(gen_d_ms)
    sink_t = cumsum_time_s_from_us(sink_d_us)
    tb_t = cumsum_time_s_from_us(tb_d_us)

    plot_cumulative(
        series=[
            ("Generator", gen_t, np.cumsum(gen_sz)),
            ("Token bucket arrivals", tb_t, np.cumsum(tb_sz)),
            ("Sink", sink_t, np.cumsum(sink_sz)),
        ],
        title=f"Exercise 2-c max supported rate ({max_rate:.2f} Mbps)",
        out_name="2c_max_rate_cumulative.png",
        base_unit="Bytes",
    )

    plot_tb_backlog(
        tb_t=tb_t,
        tb_tokens=tb_tokens,
        tb_backlog=tb_backlog,
        title=f"Exercise 2-c TB/Backlog at max rate ({max_rate:.2f} Mbps)",
        out_name="2c_max_rate_backlog.png",
        base_unit="Bytes",
    )

    return max_rate


def main():
    parser = argparse.ArgumentParser(description="Run ECE466 Lab2b experiments and generate required plots")
    parser.add_argument("--only", choices=["1a", "2b", "2c", "all"], default="all")
    parser.add_argument("--count", type=int, default=500, help="Packets per scenario")
    parser.add_argument("--bucket-rate-mbps", type=float, default=10.0)
    args = parser.parse_args()

    ensure_dirs()

    if args.only in ("1a", "all"):
        for scenario in SCENARIOS:
            run_exercise_1a_scenario(scenario, packet_count=args.count)

    if args.only in ("2b", "all"):
        for scenario in SCENARIOS:
            run_exercise_2b_scenario(
                scenario,
                packet_count=args.count,
                bucket_rate_bytes_per_sec=int(args.bucket_rate_mbps * 1_000_000 / 8.0),
                bucket_size_bytes=1250,
            )

    if args.only in ("2c", "all"):
        max_rate = run_exercise_2c(bucket_rate_mbps=args.bucket_rate_mbps)
        print(f"Estimated max supported arrival rate: {max_rate:.2f} Mbps")


if __name__ == "__main__":
    main()
