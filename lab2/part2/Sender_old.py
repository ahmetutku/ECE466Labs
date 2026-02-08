import socket
import sys
import time

host = sys.argv[1]

addr = (host, 4444)

with open('poisson-lab2a.data', 'r') as file:
    lines = [[int(j) for j in i.strip().split('\t')] for i in file.readlines()]

# Create a UDP socket
sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)

starttime = time.time()
for _, rel_ms, size in lines:
    sendtime = starttime + rel_ms/1000
    time.sleep(max(sendtime - time.time(), 0))

    message = 'a'*size
    message = message.encode('utf-8')  # convert string to bytes
    sock.sendto(message, addr)  # Send the datagram

sock.close()
