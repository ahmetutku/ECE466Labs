import pandas as pd
import sys

############################################################################
# The program reads an input file "data.txt"  that has entries of the form
#  0    0.000000    I   536 98.190  92.170	92.170
#  4    133.333330  P   152 98.190  92.170	92.170
#  1    33.333330   B   136 98.190  92.170	92.170
#
# The file is read line-by-line, values are parsed and assigned to variables,
# values are  displayed, and then written to a file with name "output.txt"
############################################################################


# Read packet trace
df = pd.read_csv(
    #"data.txt",   # file to load
    sys.argv[1],   # file to load
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
    ],
    # pandas can normally infer the type of each column,
    # but we explicate them just in case
    dtype={
        'display_idx': 'Int32', 'type': 'category',
        'time_ms': 'Float64', 'size_B': 'Int32',
    },
)

print(df)

df[["display_idx", "time_ms", "type", "size_B"]].to_csv(
    "output.txt", sep="\t", index=False)

dfI = df[df['type'] == 'I']
iavg = dfI['size_B'].sum() / len(dfI)

dfP = df[df['type'] == 'P']
pavg = dfP['size_B'].sum() / len(dfP)

dfB = df[df['type'] == 'B']
bavg = dfB['size_B'].sum() / len(dfB)

print(f"Average I size: {iavg}, Average P size: {pavg}, Average B size: {bavg}")
