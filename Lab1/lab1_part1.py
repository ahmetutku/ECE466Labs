`# /// script
# requires-python = ">=3.9"
# dependencies = [
#     "matplotlib>=3.5",
#     "pandas>=1.4",
# ]
# ///
import pandas as pd
import matplotlib.pyplot as plt

# Parameters
file_name = "poisson1.data"  # name of the table file to read
initial_time_us = 0.0        # start time of the plot, in microseconds
window_size_us = 10000.0   # size of one window, in microseconds
num_windows = 100            # the number of windows to compute

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
        "packet_no",  # packet number
        "time_us",    # timestamp, in microseconds
        "size_B",     # packet size, in bytes
    ]
)

# Shift the initial time to zero
df["time_us"] = df["time_us"] - initial_time_us

# Separate packets into timeslots, we use floor(time / window size), so
# the first few timeslots have `time_us` in [0, win), [win, 2 win), etc.
df["timeslot"] = (df["time_us"] // window_size_us).astype(int)

# Now, group together all rows with the same `timeslot`, then add them up
bytes_per_slot = df.groupby("timeslot")["size_B"].sum()

# Fill missing entries, which occurs if any slot contains no packets
bytes_per_slot = bytes_per_slot.reindex(range(num_windows+1), fill_value=0)

# Convert `timeslots` back to times, and `bytes_per_slot` to the correct unit.
# Here, we set `times` to the beginning of each slot. The `fill_between` should
# set its step to `post`, so that the values in the middle snap to the "left",
# i.e., the beginning of the slots.
times = bytes_per_slot.index * window_size_us / time_unit_multiplier
sizes = bytes_per_slot.values / size_unit_multiplier

# Plot the data
plt.figure(figsize=(8, 4))
plt.fill_between(times, sizes, step="post")
plt.ylim(0)

# Set title and labels so that screenshots contain them
plt.title("Aggregated Bytes per Time Window")
plt.xlabel(f"Time ({time_unit})")
plt.ylabel(f"{size_unit}s")

plt.tight_layout()
plt.show()
`