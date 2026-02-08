import socket
import sys

if len(sys.argv) != 3:
    print(f"Usage: {sys.argv[0]} <hostname> <message>")
    sys.exit(1)
host = sys.argv[1]
message = sys.argv[2].encode('utf-8')  # convert string to bytes

addr = (host, 4444)

# Create a UDP socket
sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)

sock.sendto(message, addr)  # Send the datagram
sock.close()
