# /// script
# requires-python = ">=3.9"
# dependencies = [
#     "matplotlib>=3.5",
#     "pandas>=1.4",
# ]
# ///
import pandas as pd
import matplotlib.pyplot as plt

# Parameters
file_name = "movietrace.data"  # the name of the table file to read
initial_frame = 0              # the first frame to use
window_size = 500              # size of one window, in frames
num_windows = 100              # the number of windows to compute

# Unit parameters, for plotting only
# KEEP THE UNITS AND MULTIPLIERS IN SYNC
size_unit = "MB"
size_unit_multiplier = 1e6  # in bytes

# Read packet trace
df = pd.read_csv(
    file_name,    # file to load
    sep=r"\s+",   # each column is space-separated
    header=None,  # the file contains no header
    # column names, with units at the back
    names=[
        "display_idx",  # frame display index
        "time_ms",      # timestamp, in milliseconds
        "type",         # frame type (I/B/P)
        "size_B",       # frame size, in bytes
        # We don't use the remaining fields, so just call them "unused"
        "unused1", "unused2", "unused3",
    ]
)

# Since we extrace the data from `df`, it shares the same indices, which
# are the transmission index
i_frame_sizes = df[df["type"] == "I"]["size_B"]  # sizes of I frames
b_frame_sizes = df[df["type"] == "B"]["size_B"]  # sizes of B frames
p_frame_sizes = df[df["type"] == "P"]["size_B"]  # sizes of P frames

###########################################################################
# Hint 1:
#   You may use `len()`, `mean()`, `max()`, `min()`, which calculate the
#   length, mean, max, min of a series. For example, `i_frame_sizes.max()`
#   will give you the size of the largest I frame. Note that `len` function
#   has to be called with `len(i_frame.sizes)`.
# Hint 2:
#   Use the `fill_between` function to graph the frame sizes as a function
#   of the frame sequence number.
# Hint 3:
#   Use the function `hist` to show the distribution of frames.
###########################################################################

#
# The following code will generates Plot 1. You need to add Plots 2 and 3.
#
fix, axes = plt.subplots(3, 1, figsize=(8, 6), sharex=True)
(ax1, ax2, ax3) = axes  # 3 vertically aligned plots

# We use transmission sequence (df.index), not display sequence (df["idx"])
slot = ((i_frame_sizes.index - initial_frame) / window_size).astype(int)
sizes = i_frame_sizes / size_unit_multiplier
bytes_per_slot = sizes.groupby(slot).sum()
bytes_per_slot = bytes_per_slot.reindex(range(num_windows+1), fill_value=0)

frames = bytes_per_slot.index * window_size  # the first frame number of a slot
# Plot with `fill_between` and `post` to create a box plot
ax1.fill_between(frames, bytes_per_slot.values, step="post")
# Set plotting parameters
ax1.set_ylabel(f"I-Frames ({size_unit}s)")
ax1.set_ylim(0)

#
# <-- Plot 2 goes here -->
#

#
# <-- Plot 3 goes here -->
#

ax3.set_xlabel(f"Frame")  # only the bottom plot gets x label
plt.tight_layout()
plt.show()
