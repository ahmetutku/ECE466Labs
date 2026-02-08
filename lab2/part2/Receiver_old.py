import socket
import time
import sys

# Create a UDP socket bound to port 4444
sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
sock.bind(("", 4444))   # "" means all local interfaces

print("Waiting for a message on UDP port 4444 ...")

results = []
starttime = -1

try:
    while True:
        data, addr = sock.recvfrom(1024)  # assuming up to 1024 bytes
        #message = data.decode('utf-8')  # Decode bytes to string

        if starttime == -1:
            starttime = time.time()
            toadd = (len(data), 0)
        else:
            toadd = (len(data), time.time() - starttime)
            starttime = time.time()

        results.append(toadd)

        #print(f"Received '{message}' from {addr}")
except KeyboardInterrupt:
    with open('output.txt', 'w') as file:
        for size, time_s in results:
            file.write(f'{size}\t{time_s*1000}\n')
    sys.exit(0)
