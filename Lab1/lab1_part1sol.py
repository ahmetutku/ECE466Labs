

import numpy as np
import pandas as pd
import matplotlib.pyplot as plt

def load_trace(path: str) -> pd.DataFrame:
    df = pd.read_csv(path, sep=r"\s+", header=None, names=["pkt", "time_us", "size_bytes"])
    df["time_s"] = df["time_us"] * 1e-6
    return df


def interarrival_stats(df: pd.DataFrame) -> tuple[float, float]:
    t = df["time_s"].to_numpy()
    iat = np.diff(t)
    return float(iat.mean()), float(iat.var())


def measured_bitrate_mbps(df: pd.DataFrame) -> float:
    t0 = float(df["time_s"].iloc[0])
    t1 = float(df["time_s"].iloc[-1])
    duration = t1 - t0
    total_bits = float(df["size_bytes"].sum() * 8)
    return (total_bits / duration) / 1e6


def bytes_in_intervals(times_s: np.ndarray, sizes_bytes: np.ndarray, start_s: float, interval_s: float,count: int = 100) -> np.ndarray:
    out = np.zeros(count, dtype=float)
    for i in range(count):
        a = start_s + i * interval_s
        b = a + interval_s
        mask = (times_s >= a) & (times_s < b)
        out[i] = sizes_bytes[mask].sum()
    return out


def pick_random_start(rng: np.random.Generator, t_min: float, t_max: float, needed: float) -> float:
    latest_start = t_max - needed
    if latest_start <= t_min:
        return t_min
    return float(rng.uniform(t_min, latest_start))


def make_three_scaled_plots(df: pd.DataFrame, title_prefix: str, out_prefix: str, rng: np.random.Generator):
    times = df["time_s"].to_numpy()
    sizes = df["size_bytes"].to_numpy()

    t_min = float(times.min())
    t_max = float(times.max())

    start1 = 0.0
    interval1 = 1.0
    v1 = bytes_in_intervals(times, sizes, start1, interval1, 100)

    plt.figure()
    plt.bar(np.arange(100), v1)
    plt.xlabel("Interval index (1 s each)")
    plt.ylabel("Bytes in interval")
    plt.title(f"{title_prefix} — Scale: 1 s bins (start = {start1:.3f} s)")
    plt.tight_layout()
    plt.savefig(f"{out_prefix}_plot1_1s.png", dpi=200)

    interval2 = 0.1
    needed2 = 100 * interval2
    start2 = pick_random_start(rng, t_min, t_max, needed2)
    v2 = bytes_in_intervals(times, sizes, start2, interval2, 100)

    plt.figure()
    plt.bar(np.arange(100), v2)
    plt.xlabel("Interval index (100 ms each)")
    plt.ylabel("Bytes in interval")
    plt.title(f"{title_prefix} — Scale: 100 ms bins (start = {start2:.3f} s)")
    plt.tight_layout()
    plt.savefig(f"{out_prefix}_plot2_100ms.png", dpi=200)

    interval3 = 0.01
    needed3 = 100 * interval3
    start3 = pick_random_start(rng, t_min, t_max, needed3)
    v3 = bytes_in_intervals(times, sizes, start3, interval3, 100)

    plt.figure()
    plt.bar(np.arange(100), v3)
    plt.xlabel("Interval index (10 ms each)")
    plt.ylabel("Bytes in interval")
    plt.title(f"{title_prefix} — Scale: 10 ms bins (start = {start3:.3f} s)")
    plt.tight_layout()
    plt.savefig(f"{out_prefix}_plot3_10ms.png", dpi=200)


def print_step1_summary(ex_name: str, df: pd.DataFrame, lam_theory: float):

    mean_iat, var_iat = interarrival_stats(df)
    bit_rate = measured_bitrate_mbps(df)

    mean_theory = 1.0 / lam_theory
    var_theory = 1.0 / (lam_theory ** 2)

    print("\n" + "=" * 70)
    print(ex_name)
    print("=" * 70)
    print(f"Theoretical lambda (packets/s): {lam_theory:.3f}")
    print(f"Theoretical mean IAT (s):       {mean_theory:.9f}")
    print(f"Theoretical var  IAT (s^2):     {var_theory:.12e}")
    print("-" * 70)
    print(f"Measured mean IAT (s):          {mean_iat:.9f}")
    print(f"Measured var  IAT (s^2):        {var_iat:.12e}")
    print(f"Measured mean bit rate (Mbps):  {bit_rate:.6f}")
    print("=" * 70)


def exercise_1a():
    pkt_size_bytes = 100.0
    target_rate_mbps = 1.0
    target_rate_Bps = (target_rate_mbps * 1e6) / 8.0  # bytes per second
    lam = target_rate_Bps / pkt_size_bytes            # packets per second (expected)

    df1 = load_trace("poisson1.data")

    print_step1_summary("Exercise 1-a — poisson1.data (fixed packet size)", df1, lam)

    rng = np.random.default_rng(466)  # reproducible random start times
    make_three_scaled_plots(
        df=df1,
        title_prefix="Exercise 1-a (poisson1.data, 100B packets)",
        out_prefix="ex1a",
        rng=rng
    )


def exercise_1b():
    lam = 1250.0  # packets per second

    df3 = load_trace("poisson3.data")
    print_step1_summary("Exercise 1-b — poisson3.data (compound Poisson sizes)", df3, lam)
    rng = np.random.default_rng(466 + 1)  # different seed than 1-a
    make_three_scaled_plots(
        df=df3,
        title_prefix="Exercise 1-b (poisson3.data, variable packet sizes)",
        out_prefix="ex1b",
        rng=rng
    )


if __name__ == "__main__":
    exercise_1a()
    exercise_1b()

    plt.show()

    print("\nSaved plot files:")
    print("  ex1a_plot1_1s.png, ex1a_plot2_100ms.png, ex1a_plot3_10ms.png")
    print("  ex1b_plot1_1s.png, ex1b_plot2_100ms.png, ex1b_plot3_10ms.png")