# /// script
# requires-python = ">=3.9"
# dependencies = [
#     "matplotlib>=3.5",
#     "pandas>=1.4",
# ]
# ///
import pandas as pd
import matplotlib.pyplot as plt

# Parameter
file_name = "BC-pAug89.TL"  # name of the table file to read

# Unit parameters, for plotting only
# KEEP THE UNITS AND MULTIPLIERS IN SYNC
time_unit = "s"
time_unit_multiplier = 1e6  # in microseconds
size_unit = "kB"
size_unit_multiplier = 1e3  # in bytes

# Read packet trace
df = pd.read_csv(
    file_name,    # file to load
    sep=r"\s+",   # each column is space-separated
    header=None,  # the file contains no header
    # column names, with units at the back
    names=[
        "time_s",  # timestamp, in seconds
        "size_B",  # packet size, in bytes
    ]
)

fix, axes = plt.subplots(3, 1, sharex=True)
(ax1, ax2, ax3) = axes  # 3 vertically aligned plots

#
# The following code will generates Plot 1. You need to add Plots 2 and 3.
#

# Plot 1 Parameters
initial_time_s = 0.0  # start time of the plot, in seconds
window_size_s = 1.0   # size of one window, in seconds
num_windows = 3000    # the number of windows to compute

slots = ((df['time_s'] - initial_time_s) / window_size_s).astype(int)
bytes_per_slot = df["size_B"].groupby(slots).sum() / size_unit_multiplier
bytes_per_slot = bytes_per_slot.reindex(range(num_windows+1), fill_value=0)
times = bytes_per_slot.index * window_size_s / time_unit_multiplier

ax1.fill_between(times, bytes_per_slot, step="post")
# Set plotting parameters
ax1.set_ylabel(f"Total packets ({size_unit}s)")
ax1.set_ylim(0)

#
# <-- Plot 2 goes here -->
#

#
# <-- Plot 3 goes here -->
#

ax3.set_xlabel(f"Time ({time_unit}s)")
plt.show()
