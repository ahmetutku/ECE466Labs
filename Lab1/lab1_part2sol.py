# /// script
# requires-python = ">=3.9"
# dependencies = [
#     "matplotlib>=3.5",
#     "pandas>=1.4",
# ]
# ///
from __future__ import annotations

import random
import pandas as pd
import matplotlib.pyplot as plt

# Parameters
file_name = "movietrace.data"   # the name of the table file to read
initial_frame = 0              # the first frame to use (transmit sequence index)
num_windows = 100              # the number of windows to compute

# Window sizes (in frames) for scaled traffic plots
W1 = 500
W2 = 50
W3 = 5

# Random seed for reproducible random start frames
RANDOM_SEED = 466

# Unit parameters, for plotting only
# KEEP THE UNITS AND MULTIPLIERS IN SYNC
size_unit = "MB"
size_unit_multiplier = 1e6  # in bytes

# Read video trace
df = pd.read_csv(
    file_name,    # file to load
    sep=r"\s+",   # each column is space-separated
    header=None,  # the file contains no header
    names=[
        "display_idx",  # frame display index
        "time_ms",      # timestamp, in milliseconds
        "type",         # frame type (I/B/P)
        "size_B",       # frame size, in bytes
        "unused1", "unused2", "unused3",
    ],
)

# Since we extract from df, the Series keeps df.index (transmission sequence index)
i_frame_sizes = df[df["type"] == "I"]["size_B"]
b_frame_sizes = df[df["type"] == "B"]["size_B"]
p_frame_sizes = df[df["type"] == "P"]["size_B"]

###########################################################################
# Template hints reminder:
# - Use len(), mean(), max(), min() on Series for stats
# - Use fill_between(step="post") for box/step-like traffic plots
# - Use hist() for distributions (if you later add a histogram part)
###########################################################################

def aggregate_bytes_per_slot(series_B: pd.Series, start: int, window: int, n_windows: int) -> pd.Series:
    """
    Group bytes into contiguous frame windows:
      slot k contains frames [start + k*window, start + (k+1)*window)
    Returns a length-(n_windows+1) Series with missing slots filled to 0,
    matching the style of the provided skeleton (groupby + reindex).
    """
    idx = series_B.index
    s = series_B.loc[idx >= start]  # keep only frames at/after start
    slot = ((s.index - start) // window).astype(int)
    bytes_per_slot = s.groupby(slot).sum()
    bytes_per_slot = bytes_per_slot.reindex(range(n_windows + 1), fill_value=0)
    return bytes_per_slot


# Make 3 vertically aligned plots (Plot 1, Plot 2, Plot 3)
fig, axes = plt.subplots(3, 1, figsize=(10, 8), sharex=False)
(ax1, ax2, ax3) = axes

# Use ALL frames for scaled traffic aggregation (recommended)
all_sizes = df["size_B"]

# Pick random starts for W2 and W3 so that 100 windows fit (like your solution)
random.seed(RANDOM_SEED)
N = len(all_sizes)

# We want 100 windows in each plot (same as template's num_windows),
# but note reindex uses range(num_windows+1), so we consider 100 windows worth of data.
needed2 = num_windows * W2
needed3 = num_windows * W3

max_start2 = max(0, N - needed2)
max_start3 = max(0, N - needed3)

start1 = initial_frame
start2 = random.randint(0, max_start2) if max_start2 > 0 else 0
start3 = random.randint(0, max_start3) if max_start3 > 0 else 0

# -------------------------
# Plot 1: bytes per 500 frames, starting at Frame 1
# -------------------------
bytes1 = aggregate_bytes_per_slot(all_sizes, start=start1, window=W1, n_windows=num_windows)
frames1 = bytes1.index * W1 + start1
ax1.fill_between(frames1, (bytes1.values / size_unit_multiplier), step="post")
ax1.set_title(f"Scaled video traffic: bytes per {W1} frames (starting at Frame {start1 + 1})")
ax1.set_ylabel(f"Traffic ({size_unit})")
ax1.set_ylim(0)
ax1.grid(True, linewidth=0.3, alpha=0.6)

# -------------------------
# Plot 2: bytes per 50 frames, random start (your content goes here)
# -------------------------
bytes2 = aggregate_bytes_per_slot(all_sizes, start=start2, window=W2, n_windows=num_windows)
frames2 = bytes2.index * W2 + start2
ax2.fill_between(frames2, (bytes2.values / size_unit_multiplier), step="post")
ax2.set_title(f"Scaled video traffic: bytes per {W2} frames (random start at Frame {start2 + 1})")
ax2.set_ylabel(f"Traffic ({size_unit})")
ax2.set_ylim(0)
ax2.grid(True, linewidth=0.3, alpha=0.6)

# -------------------------
# Plot 3: bytes per 5 frames, random start (your content goes here)
# -------------------------
bytes3 = aggregate_bytes_per_slot(all_sizes, start=start3, window=W3, n_windows=num_windows)
frames3 = bytes3.index * W3 + start3
ax3.fill_between(frames3, (bytes3.values / size_unit_multiplier), step="post")
ax3.set_title(f"Scaled video traffic: bytes per {W3} frames (random start at Frame {start3 + 1})")
ax3.set_ylabel(f"Traffic ({size_unit})")
ax3.set_ylim(0)
ax3.grid(True, linewidth=0.3, alpha=0.6)

ax3.set_xlabel("Frame number (start of each window)")
plt.tight_layout()
plt.show()