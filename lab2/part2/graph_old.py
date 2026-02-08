import matplotlib.pyplot as plt
import sys

with open('poisson-lab2a.data', 'r') as file:
    real = [[float(j) for j in i.strip().split('\t')] for i in file.readlines()]

with open('output.txt', 'r') as file:
    sim = [[float(j) for j in i.strip().split('\t')] for i in file.readlines()]

int_sim = []
intt = 0
#cumsize = 0
for size, t in sim:
    intt += t
    #cumsize += size
    int_sim.append((size, intt))

#int_real = []
#cumsize = 0
#for _, t, size in real:
#    cumsize += size
#    int_real.append((cumsize, t))


sim_data = []
real_data = []
diffs = []

max_bin = int(max([i[1] for i in real])) + 10
for thres in range(1,max_bin):
    sim_sum = sum([i[0] for i in int_sim if i[1] < thres])
    real_sum = sum([i[2] for i in real if i[1] < thres])
    diff = real_sum - sim_sum
    diffs.append(diff)
    sim_data.append(sim_sum)
    real_data.append(real_sum)

plt.figure(figsize=(8, 4))
plt.fill_between(range(1,max_bin), diffs, step="post")
plt.title("Difference between real acc.size and simulated acc.size")  # real is poisson-lab2a.data, simulated is output.txt
plt.xlabel("time (ms)")
plt.ylabel("size (B)")
plt.tight_layout()
plt.show()


bins = range(1, max_bin)
plt.bar(bins, sim_data, alpha=0.5, label='sim')
plt.bar(bins, real_data, alpha=0.5, label='real')
plt.legend()
plt.xlabel("time (ms)")
plt.ylabel("acc.size (B)")
plt.show()



improvements = []

with open('output.txt', 'r') as file:
    sim_new = [[float(j) for j in i.strip().split('\t')] for i in file.readlines()]
with open('output_old.txt', 'r') as file:
    sim_old = [[float(j) for j in i.strip().split('\t')] for i in file.readlines()]

for new, old in zip(sim_new, sim_old):
    improvements.append(new[1] - old[1])


plt.figure(figsize=(8, 4))
plt.fill_between(range(len(sim_new)), improvements, step="post")
plt.title("Delay difference between improved and old configuration")
plt.xlabel("Packet")
plt.ylabel("time (ms)")
plt.tight_layout()
plt.show()
