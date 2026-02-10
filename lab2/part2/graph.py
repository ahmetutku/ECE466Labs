import matplotlib.pyplot as plt
import sys

with open('poisson-lab2a.data', 'r') as file:
    real = [[float(j) for j in i.strip().split('\t')] for i in file.readlines()]

with open('output.txt', 'r') as file:
    sim = [[float(j) for j in i.strip().split('\t')] for i in file.readlines()[1:]]
    sim = [[i[1], i[0]/1000] for i in sim]

int_sim = []
intt = 0
for size, t in sim:
    intt += t
    int_sim.append((size, intt))


sim_data = []
real_data = []
diffs = []

max_bin = int(max([i[1] for i in real])) + 10
for thres_int in range(0,max_bin):
    thres = thres_int + 0.5
    sim_sum = sum([i[0] for i in int_sim if i[1] < thres])
    real_sum = sum([i[2] for i in real if i[1] < thres])
    diff = real_sum - sim_sum
    diffs.append(diff)
    sim_data.append(sim_sum)
    real_data.append(real_sum)

bins = [0.5+i for i in range(0,max_bin)]

plt.figure(figsize=(8, 4))
plt.fill_between(bins, diffs, step="post")
plt.title("Difference between real acc.size and simulated acc.size")  # real is poisson-lab2a.data, simulated is output.txt
plt.xlabel("time (ms)")
plt.ylabel("size (B)")
plt.tight_layout()
plt.show()


plt.bar(bins, sim_data, alpha=0.5, label='sim')
plt.bar(bins, real_data, alpha=0.5, label='real')
plt.legend()
plt.xlabel("time (ms)")
plt.ylabel("acc.size (B)")
plt.show()
