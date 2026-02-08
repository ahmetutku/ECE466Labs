# /// script
# requires-python = ">=3.9"
# dependencies = [
#     "matplotlib>=3.5",
#     "pandas>=1.4",
#     "numpy>=1.20",
# ]
# ///
from __future__ import annotations

import numpy as np
import pandas as pd
import matplotlib.pyplot as plt

# ============================================================
# Parameters
# ============================================================
file_name = "BC-pAug89.TL"  # name of the table file to read

# Random seed for reproducible random start times
RNG_SEED = 466

# Plot window sizes and points (scaled views)
N_POINTS = 100
W1 = 1.0     # 1 s bins
W2 = 0.1     # 100 ms bins
W3 = 0.01    # 10 ms bins

# Unit parameters, for plotting only
# KEEP THE UNITS AND MULTIPLIERS IN SYNC
time_unit = "s"
size_unit = "kB"
size_unit_multiplier = 1e3  # in bytes


# ============================================================
# Helper: aggregate bytes in time windows (template-style)
# ============================================================
def bytes_per_time_slot(df_in: pd.DataFrame, start_s: float, window_s: float, n_windows: int) -> pd.Series:
    """
    Group bytes into contiguous time windows:
      slot k contains packets with times in [start_s + k*window_s, start_s + (k+1)*window_s)

    Returns a length-(n_windows+1) Series (like the lab skeleton) with empty slots filled to 0.
    Values are returned in BYTES (not scaled).
    """
    df = df_in.copy()

    # Keep only the time range we need (faster + ensures slot indices are in range)
    end_s = start_s + n_windows * window_s
    df = df[(df["time_s"] >= start_s) & (df["time_s"] < end_s)]

    # Assign each packet to a slot number
    slots = ((df["time_s"] - start_s) / window_s).astype(int)

    # Sum bytes per slot
    bytes_slot = df["size_B"].groupby(slots).sum()

    # Fill missing slots with 0 and force fixed length
    bytes_slot = bytes_slot.reindex(range(n_windows + 1), fill_value=0)

    return bytes_slot


# ============================================================
# Main
# ============================================================
df = pd.read_csv(
    file_name,
    sep=r"\s+",
    header=None,
    names=["time_s", "size_B"],
)

# Ensure time is sorted (some traces may already be sorted, but this is safe)
df = df.sort_values("time_s").reset_index(drop=True)

rng = np.random.default_rng(RNG_SEED)

fig, axes = plt.subplots(3, 1, figsize=(10, 8), sharex=False)
(ax1, ax2, ax3) = axes

# ------------------------------------------------------------
# Plot 1 (given in skeleton idea): 1s bins from t=0
# ------------------------------------------------------------
initial_time_s = 0.0
bytes1 = bytes_per_time_slot(df, start_s=initial_time_s, window_s=W1, n_windows=N_POINTS)
times1 = bytes1.index * W1 + initial_time_s

ax1.fill_between(times1, (bytes1.values / size_unit_multiplier), step="post")
ax1.set_title(f"Scaled view: Bytes per {W1:.2f} s interval ({N_POINTS} points), start t={initial_time_s:.2f} s")
ax1.set_ylabel(f"Bytes ({size_unit})")
ax1.set_xlabel(f"Time ({time_unit})")
ax1.set_ylim(0)
ax1.grid(True, linewidth=0.3, alpha=0.6)

# ------------------------------------------------------------
# Plot 2: 100ms bins, random start (your content)
# ------------------------------------------------------------
t_min = float(df["time_s"].iloc[0])
t_max = float(df["time_s"].iloc[-1])

needed2 = N_POINTS * W2
latest_start2 = max(t_min, t_max - needed2)
start2 = float(rng.uniform(t_min, latest_start2)) if latest_start2 > t_min else t_min

bytes2 = bytes_per_time_slot(df, start_s=start2, window_s=W2, n_windows=N_POINTS)
times2 = bytes2.index * W2 + start2

ax2.fill_between(times2, (bytes2.values / size_unit_multiplier), step="post")
ax2.set_title(f"Scaled view: Bytes per {W2:.2f} s interval ({N_POINTS} points), start t={start2:.2f} s")
ax2.set_ylabel(f"Bytes ({size_unit})")
ax2.set_xlabel(f"Time ({time_unit})")
ax2.set_ylim(0)
ax2.grid(True, linewidth=0.3, alpha=0.6)

# ------------------------------------------------------------
# Plot 3: 10ms bins, random start (your content)
# ------------------------------------------------------------
needed3 = N_POINTS * W3
latest_start3 = max(t_min, t_max - needed3)
start3 = float(rng.uniform(t_min, latest_start3)) if latest_start3 > t_min else t_min

bytes3 = bytes_per_time_slot(df, start_s=start3, window_s=W3, n_windows=N_POINTS)
times3 = bytes3.index * W3 + start3

ax3.fill_between(times3, (bytes3.values / size_unit_multiplier), step="post")
ax3.set_title(f"Scaled view: Bytes per {W3:.2f} s interval ({N_POINTS} points), start t={start3:.2f} s")
ax3.set_ylabel(f"Bytes ({size_unit})")
ax3.set_xlabel(f"Time ({time_unit})")
ax3.set_ylim(0)
ax3.grid(True, linewidth=0.3, alpha=0.6)

plt.tight_layout()
plt.show()