import subprocess
import socket
import time
import struct
import threading
import tqdm
from collections import defaultdict
import matplotlib.pyplot as plt
import math

SERVER_PORT = 5555
CLIENT_PORT = 5556
#COMMAND = ("python3", "blackbox.py", f"--inport={SERVER_PORT}", "10000", "1e3", "20")
COMMAND = ("python3", "blackbox.py", f"--inport={SERVER_PORT}", "400", "inf", "10")
#COMMAND = ("python3", "blackbox2.py", f"--inport={SERVER_PORT}")
#COMMAND = ("python3", f"blackbox2.py --inport={SERVER_PORT}")

def to_byte_array(value):  # this was messing up my linter
    """
    Convert an integer to a 4-byte big-endian array.
    :param value: Integer value to convert.
    :return: 4-byte big-endian representation of the integer.
    """
    result = bytearray(4)
    result[3] = (value >> (8*0)) & 0xFF
    result[2] = (value >> (8*1)) & 0xFF
    result[1] = (value >> (8*2)) & 0xFF
    result[0] = (value >> (8*3)) & 0xFF
    return result


#template = bytearray(400)
#template[0:2] = to_byte_array(CLIENT_PORT)[2:4]
#def genpkt(size, sequence):
#    global template
#    template[2:6] = to_byte_array(sequence)
#    return template

def genpkt(size, sequence):
    #assert size >= 6
    #assert size <= 1480
    result = bytearray(size)
    result[0:2] = to_byte_array(CLIENT_PORT)[2:4]
    result[2:6] = to_byte_array(sequence)
    return result

def sendpkt(sock, size, sequence):
    message = genpkt(size, sequence)
    addr = ('localhost', SERVER_PORT)
    sock.sendto(message, addr)

def transmit(sock, event, v_n, v_l, v_r, ret):
    global starttime
    # n packets, of l size each, r is average bit rate (in kbps)
    event.clear()  # ensure its clear first. it being set means its completed

    v_r = v_r*1000
    waittime = v_l/v_r

    t = starttime
    for i in range(v_n):
        sendpkt(sock, v_l, i)
        ret[i] = time.time()
        t += waittime
        #time.sleep(max(t - time.time(), 0))  # this seems to be the problem ?
        while t > time.time():
            pass

    for i in ret.keys():
        ret[i] = (ret[i] - starttime)*1000

    event.set()
    print("transmission done, event set")


def recv(sock, event, ret):
    global starttime
    #bar = tqdm.tqdm()

    while True:
        try:
            data, addr = sock.recvfrom(1500)
        except TimeoutError:
            data, addr = (None, None)
            if event.is_set():
                break

        if data is not None:
            seq = struct.unpack(">i", data[2:6])[0]
            size = len(data)

            t = time.time()
            ret[seq] = t

            #bar.update(1)  # candy

    for i in ret.keys():
        ret[i] = (ret[i] - starttime)*1000  # normalize to first recved packet. this hopefully reduces the delay caused by localhost transmission time, unless its desired


sendsock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
recvsock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
recvsock.bind(("", CLIENT_PORT))
recvsock.settimeout(5)  # or else recv will halt

starttime = None  # raises typerror if not initialized
def test(v_n, v_l, v_r):
    global sendsock, recvsock
    sendtimes = {}
    recvtimes = {}
    event = threading.Event()
    blackbox = subprocess.Popen(COMMAND)
    time.sleep(0.1)  # wait for blackbox initialization

    t1 = threading.Thread(target=transmit, args=(sendsock, event, v_n, v_l, v_r, sendtimes))
    t2 = threading.Thread(target=recv, args=(recvsock, event, recvtimes))

    global starttime
    starttime = time.time()
    t2.start()  # start the receiver before the sender
    t1.start()
    t1.join()
    t2.join()

    blackbox.kill()

    final = []
    for i in range(v_n):
        final.append((sendtimes.get(i, None), recvtimes.get(i, None)))


    return final

r1 = test(100, 400, 10)
r2 = test(100, 400, 1000)
r3 = test(100, 400, 10000)

def plot(data):
    #print(data)
    x = list(range(len(data)))
    y1 = [t[0] for t in data]
    y2 = [t[1] for t in data]

    plt.plot(x, y1)
    plt.plot(x, y2)
    plt.xlabel('Packet sent/received')
    plt.ylabel('Time (ms)')
    plt.title("Time when each packet was sent/received")

for i in (r1, r2, r3):
    plot(i)
    plt.show()


sendsock.close()
recvsock.close()
