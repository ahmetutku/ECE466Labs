Part 1: there is only code needed.

Part 2:
sim -> my traffic generator
real -> the given poisson data

2-c: fig 2
there is an improvement in latency in the improved output, but it is not shown in the graphs as the bins are cenered around the times when the packets are sent. this means a slight improvement in latency does not push the threshold past the binning into the correct bin.

I am receiving packets "earlier" than I am supposed to be sending them. My hypothesis for this occuring is that the localhost network "warms up" after the first udp packet sent, and only that packet is hit by an increased latency. since that packet is t=0, it being the only packet with latency pushes all the other packets forwards relatively in time

2-d: fig 1
I am not seeing any packet losses, since the resulting difference in sim/real accumalated packets is 0, suggesting all packets reach their destination. this is seen in my fig 1

fig1 description:
This shows the difference in accumalated packets between real and simmed packets. As shown, every bar is negative, meaning simmed packets accumalate more bandwidth than real packets, having its packets appear in earlier bins. This is due to the issue described above. Furthermore, the difference at the end is 0, suggesting all packets reach their destination and no packets are lost.

fig2 description:
This is a histogram showing the underlying data for fig1, of accumalated packets over time for simmed and real data. Here it's even more obvious that some packets belonging to a later bin are classified into an earlier bin in the simmed data.
