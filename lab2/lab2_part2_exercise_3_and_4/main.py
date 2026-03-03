import math
import matplotlib.pyplot as plt

with open("BC-pAug89.TL") as file:
    bctl = [i.strip().split() for i in file.readlines()[:1000]]
    bctl = [(float(i[0]), int(i[1])) for i in bctl]
with open("movietrace.data") as file:
    movietrace = [i.strip().split('\t') for i in file.readlines()[:1000]]
    movietrace.sort(key=lambda x: int(x[0]))
    movietrace = [(float(i[1])/1000, int(i[3])) for i in movietrace]

def packetize(trace, max_size=1480):
    toret = []
    for i in trace:
        for _ in range(i[1]//max_size):
            toret.append((i[0], max_size))
        if i[1]%max_size:
            toret.append((i[0], i[1]%max_size))
    return toret


# (time, size)

# no delay over 100ms
# no overflows
# peak rate > rate > average rate

def differentiate(trace):  # d over time
    lasttime = 0
    toret = []
    for time, val in trace:
        toret.append((time - lasttime, val))
        lasttime = time
    return toret

def cum_size(trace):
    total = 0
    toret = []
    for time, val in trace:
        total += val
        toret.append((time, total))
    return toret

def average_peak(trace):
    maxtime = max([i[0] for i in trace])
    sumsize = sum([i[1] for i in trace])
    average = sumsize / maxtime
    peak = max([i[1]/i[0] for i in differentiate(trace)[1:]])  # the first one has 0 time

    return average, peak

def diff(trace1, trace2):
    toret = []
    for (time1, size1), (time2, size2) in zip(trace1, trace2):
        assert time1 == time2
        toret.append((time1, abs(size1-size2)))
    return toret

def bsearch(trace, t, start=None, end=None):
    # binary search for index
    if start is None and end is None:
        if t <= trace[0][0]:
            return 0
        if t >= trace[-1][0]:
            return len(trace)-1

    if start is None:
        start = 0
    if end is None:
        end = len(trace)

    i = start + (end-start)//2
    if trace[i+1][0] > t:
        if trace[i][0] <= t:
            return i
    
    if trace[i][0] > t:
        return bsearch(trace, t, start, i)
    else:
        return bsearch(trace, t, i, end)

def index(trace, t):
    # this is for accum. size only
    #assert t >= 0 and t <= max([i[0] for i in trace])
    assert t >= 0

    ind = bsearch(trace, t)
    if ind == len(trace) - 1:
        return trace[-1][1]

    if trace[ind][0] == t:
        return trace[ind][1]

    one = trace[ind+1]
    two = trace[ind]
    slope = (two[1] - one[1]) / (two[0] - one[0])
    return one[1] + (t - one[0]) * slope


def backlog(hi, lo):
    timestamps = list(set([i[0] for i in hi] + [i[0] for i in lo]))
    timestamps.sort()
    toret = []
    for t in timestamps:
        toret.append((t, index(hi, t) - index(lo, t)))
    return toret

def transpose(trace):
    return [[i[1], i[0]] for i in trace]

def delay(hi, lo):
    return transpose(backlog(transpose(lo), transpose(hi)))

def maxind(trace, ind):
    return max([i[ind] for i in trace])

def multi_tb_run(trace, *tbs):
    toret = []
    buckets = [i.size for i in tbs]
    curtime = 0
    for time, size in trace:
        if time > curtime:
            for ind, tb in enumerate(tbs):
                buckets[ind] += (time-curtime) * tb.rate
                buckets[ind] = min(buckets[ind], tb.size)
            curtime = time

        if all([i >= size for i in buckets]):
            buckets = [i-size for i in buckets]
        else:
            waittime = max([(size-bucket)/tb.rate for bucket, tb in zip(buckets, tbs)])
            for ind, tb in enumerate(tbs):
                buckets[ind] += waittime * tb.rate
            buckets = [i-size for i in buckets]
            curtime += waittime

        toret.append((curtime, size))
    return toret

class TokenBucket:
    def __init__(self, rate, size):
        self.rate = rate
        self.size = size

    #def service_curve(self, t):
    #    return self.size + self.rate*t

    #def run(self, trace):
    #    # inputs cum time, instantaneous size
    #    # outputs time same as trace, but linear interpolation
    #    # outputs cum time, instantaneous size
    #    toret = []
    #    bucket = self.size
    #    curtime = 0
    #
    #    for time, size in trace:
    #        if time > curtime:
    #            bucket += (time-curtime) * self.rate  #  wait until we receive this packet
    #            curtime = time
    #
    #        if bucket >= size:
    #            # if bucket is right size, send immediately
    #            bucket -= size
    #        else:
    #            # wait until we have enough in the bucket, then send
    #            waittime = (size - bucket) / self.rate
    #            curtime += waittime
    #            bucket = 0
    #        toret.append((curtime, size))
    #
    #    return toret
    def run(self, trace):
        return multi_tb_run(trace, self)


def plot_cum(trace):
    plt.plot(*zip(*cum_size(trace)))


def nonzero_val(trace):
    toret = []
    # takes accum.time and outputs when size is nonzero
    for ind, (time, size) in enumerate(trace[:-1]):
        if size > 0 or trace[ind+1][1] > 0:
            start = time
            end = trace[ind+1][0]
            if toret and toret[-1][1] == start:
                toret[-1][1] = end
            else:
                toret.append([start, end])
    return toret


PART1 = 1
PART2 = 1
PART3 = 1

if PART1:
    print("BCTL: Average {}, Peak {}".format(*average_peak(bctl)))
    print("movietrace: Average {}, Peak {}".format(*average_peak(movietrace)))

bctl = packetize(bctl)
movietrace = packetize(movietrace)

if PART2:
    print("3-a:")
    tb = TokenBucket(3e5, 0)
    run = tb.run(bctl)
    print("BCTL:")
    plot_cum(run)
    plot_cum(bctl)
    bl = backlog(cum_size(bctl), cum_size(run))
    print("delay", maxind(delay(cum_size(bctl), cum_size(run)), 0))
    plt.plot(*zip(*bl))
    plt.xlabel("Time (s)")
    plt.ylabel("Size (b)")
    plt.title("3-a BCTL A, B, D")
    plt.show()


    tb = TokenBucket(9e6, 0)
    run = tb.run(movietrace)
    print("movietrace:")
    plot_cum(run)
    plot_cum(movietrace)
    bl = backlog(cum_size(movietrace), cum_size(run))
    print("delay", maxind(delay(cum_size(movietrace), cum_size(run)), 0))
    plt.plot(*zip(*bl))
    plt.xlabel("Time (s)")
    plt.ylabel("Size (b)")
    plt.title("3-a movietrace A, B, D")
    plt.show()


    print("3-b:")
    tb = TokenBucket(149543, 10e4)
    run = tb.run(bctl)
    print("BCTL")
    plot_cum(run)
    plot_cum(bctl)
    bl = backlog(cum_size(bctl), cum_size(run))
    print("delay", maxind(delay(cum_size(bctl), cum_size(run)), 0))
    plt.plot(*zip(*bl))
    plt.xlabel("Time (s)")
    plt.ylabel("Size (b)")
    plt.title("3-b BCTL A, B, D")
    plt.show()


    tb = TokenBucket(1477313, 74e5)
    run = tb.run(movietrace)
    print("movietrace:")
    plot_cum(run)
    plot_cum(movietrace)
    bl = backlog(cum_size(movietrace), cum_size(run))
    print("delay", maxind(delay(cum_size(movietrace), cum_size(run)), 0))
    plt.plot(*zip(*bl))
    plt.xlabel("Time (s)")
    plt.ylabel("Size (b)")
    plt.title("3-b movietrace A, B, D")
    plt.show()


if PART3:
    print("4-b")
    print("movietrace:")
    tb1 = TokenBucket(630e4, 1480*3)
    tb2 = TokenBucket(200e4, 85e5)
    out = multi_tb_run(movietrace, tb1, tb2)
    plot_cum(movietrace)
    plot_cum(out)
    bl = backlog(cum_size(movietrace), cum_size(out))
    print("delay", maxind(delay(cum_size(movietrace), cum_size(out)), 0))
    plt.plot(*zip(*bl))
    plt.xlabel("Time (s)")
    plt.ylabel("Size (b)")
    plt.title("4-a/b movietrace A, B, D")
    plt.show()

    bltime = sum([i[1]-i[0] for i in nonzero_val(bl)])
    print(f"backlog percentage: {bltime/bl[-1][0] * 100}%")
    print(f"longest backlog: {max([i[1]-i[0] for i in nonzero_val(bl)])}")

# in 3-a, I set size to 0 and I set rate to a high enough number to transfer enough to eliminate delays over 100ms
# in 3-b, I set rate to just over the average rate and tune the token bucket size so the delay is low
# the movietrace has both higher rate and higher inst.rate requirements due to simply being more data transferred each second
# the bctl trace is less bursty (lower peak to average ratio) and thus requires less traffic shaping
