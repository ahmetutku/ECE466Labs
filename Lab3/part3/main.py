import matplotlib.pyplot as plt
import socket
import time
import sys
import collections
import threading

SIM_FALSE = 0

starttime_false = -1
traces_false = collections.defaultdict(list)

with open("poisson3.data", 'r') as file:
    poisson_original = [(int(t)/1e6, int(size)*8) for seq, t, size in [i.split(' ') for i in file.readlines()]]
    # (cum-time, size) in (seconds, bits)
    #print(max([i[1] for i in poisson_original]))

def average_rate_of(trace):
    return sum([i[1] for i in trace]) / max([i[0] for i in trace])

def generate_traffic(avg_rate_mb):
    avg_rate = avg_rate_mb * 1e6
    ratio = avg_rate / average_rate_of(poisson_original)  # >1 if requesting more average rate than original poisson
    toret = [(i / ratio, j) for i, j in poisson_original]
    return toret

def plot(trace):
    plt.fill_between([i[0] for i in trace], [i[1] for i in trace])

qsize = 100e3 * 8
rate = 10e6
#rate = 19e6
# queue = 100kb
# transmission rate is 10Mbps

sendsock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
def send(size, tag):
    #assert size%8 == 0
    #assert len(str(tag).encode()) == 1
    message = chr(tag).encode() + b'x'*((size//8)-1)
    addr = ('localhost', 4444)
    sendsock.sendto(message, addr)

    if SIM_FALSE:
        global starttime_false
        if starttime_false == -1:
            starttime_false = time.time()
        traces_false[tag].append((time.time() - starttime_false, size))

def recv(sock):
    data, addr = sock.recvfrom(1500)
    return len(data)*8, data[0]


# tag: (trace, weight)
#traffic = {1: (generate_traffic(8), 1), 2: (generate_traffic(6), 1), 3: (generate_traffic(2), 1)}  # 3b
#traffic = {1: (generate_traffic(8), 3), 2: (generate_traffic(6), 1), 3: (generate_traffic(2), 1)}  # 3c
#traffic = {1: (generate_traffic(5), 1), 2: (generate_traffic(5), 1)}  # 3d-1
#traffic = {1: (generate_traffic(5), 1), 2: (generate_traffic(9), 1)}  # 3d-2
traffic = {1: (generate_traffic(5), 1), 2: (generate_traffic(15), 1)}  # 3d-3

#traffic = {1: (generate_traffic(0.01), 1)}
#traffic = {1: (generate_traffic(4), 1)}
#traffic = {1: (generate_traffic(0.8), 1), 2: (generate_traffic(0.6), 1), 3: (generate_traffic(0.2), 1)}
maintrace = []

for tag, (trace, _) in traffic.items():
    for t, size in trace:
        maintrace.append((t, size, tag))
maintrace.sort(key=lambda x: x[0])  # sort by time, I know sorting ordered lists could be faster but this works

class sumqueue(collections.deque):
    # can only use popleft, append to track
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.sum = sum(self)
    def popleft(self):
        toret = super().popleft()
        self.sum -= toret
        return toret
    def append(self, item):
        self.sum += item
        return super().append(item)

def sendtrace(trace):
    #qs = collections.defaultdict(collections.deque)
    qs = collections.defaultdict(sumqueue)
    quanta = 1500*8  # larger than max packet
    dc = collections.defaultdict(int)

    time_per_bit = 1/rate

    # send main trace
    starttime = time.time()

    emptyqueue = True
    
    for trace_ind, (cum_time, size, tag) in enumerate(trace):
        sendtime = starttime + cum_time  # the real_life time that this packet was recved by the scheduler

        # if there is no queues, wait until trace
        # (if there are queues, then last round sent nothing)
        #if not any(q for q in qs.values()):
        if emptyqueue:
            time.sleep(max(sendtime - time.time(), 0))

        if qs[tag].sum + size <= qsize:
        #if sum(qs[tag]) + size <= qsize:
            qs[tag].append(size)  # enqueue this no matter what, it will be dequeued this round if theres enough capacity
            # otherwise drop
        else:
            continue

        while trace_ind == len(trace)-1 or (starttime+(trace[trace_ind+1][0]) > time.time()):
            # we elapse time until the next trace or until the all the queues are sent
            total_sent = 0
            sentstarttime = time.time()
            for inst_tag, (_, weight) in traffic.items():
                dc[inst_tag] += weight * quanta
            for inst_tag in traffic.keys():
                while qs[inst_tag] and dc[inst_tag] >= qs[inst_tag][0]:
                    size = qs[inst_tag].popleft()

                    send(size, inst_tag)
                    #threading.Thread(target=send, args=(size, inst_tag)).start()

                    total_sent += size
                    dc[inst_tag] -= size

                if not qs[inst_tag]:  # if queue is empty, no dc
                    dc[inst_tag] = 0
            if total_sent == 0:
                emptyqueue = True
                break
            else:
                emptyqueue = False

            sentendtime = sentstarttime + total_sent * time_per_bit
            waittime = sentendtime - time.time()
            #print(total_sent * time_per_bit)
            if waittime < 0:
                # we sent such a small amount of things that it took longer to check what is being sent than it took to send them
                # this will happen when there is no queue or the only entry (the one we just got) was just sent. we just have to not wait for it
                # it will enter the next trace entry if this is the case, which will wait because the queue is empty
                # that waiting will negate the effect of this desync, so we dont have to optimize the code above
                #print("DESYNC!")
                pass
            else:
                time.sleep(waittime)

        # otherwise
        # this was queued because of the wait
        # it stays queued

def recvtrace():
    print("ready to receive")
    if SIM_FALSE:
        return traces_false

    starttime = -1
    results = collections.defaultdict(list)
    try:
        with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as sock:
            sock.bind(("", 4444))
            while True:
                size, tag = recv(sock)
                t = time.time()

                if starttime == -1:
                    starttime = t
                results[tag].append((t - starttime, size))
    except KeyboardInterrupt:
        return results

#print(rate)
#print(average_rate_of(poisson_original))
#print(average_rate_of(traffic[1][0]))

if "send" in sys.argv:
    sendtrace(maintrace)
    print("done sending")
if "recv" in sys.argv:
    results = recvtrace()

    min_end_time = min([trace[-1][0] for trace in results.values()])
    graph_end_time = min(min_end_time, 2)
    
    for tag, trace in results.items():
        t, size = zip(*[(t, size) for t, size in trace if t <= graph_end_time])

        cum_bits = []
        total = 0
        for s in size:
            total += s
            cum_bits.append(total)

        plt.plot(t, cum_bits, label=str(tag))

        placeind = int(len(t) * (5 - tag)/5)
        plt.annotate(str(tag), xy=(t[placeind], cum_bits[placeind]))

    plt.xlabel('Time (s)')
    plt.ylabel('Cum Size (b)')
    plt.title('Cumalative size according to time and tag')
    plt.legend()
    plt.show()


    for tag, trace in results.items():
        t, size = zip(*[(t, size) for t, size in trace if t <= graph_end_time])

        cum_pkts = []
        total = 0
        for s in size:
            total += 1
            cum_pkts.append(total)

        plt.plot(t, cum_pkts, label=str(tag))

        placeind = int(len(t) * (5 - tag)/5)
        plt.annotate(str(tag), xy=(t[placeind], cum_pkts[placeind]))

    plt.xlabel('Time (s)')
    plt.ylabel('Packets')
    plt.title('Packets transmitted according to time and tag')
    plt.legend()
    plt.show()


    for tag in traffic.keys():
        trunc_data = [(t, size) for t, size in results[tag] if t <= min_end_time]
        total_bits = sum([i[1] for i in trunc_data])
        duration = max([i[0] for i in trunc_data])
        print(f"Tag: {tag}, Truncated Rate: {total_bits/duration/1e6} Mbps")



#sendsock.close()
