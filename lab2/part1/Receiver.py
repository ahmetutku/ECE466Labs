import socket

# Create a UDP socket bound to port 4444
sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
sock.bind(("", 4444))   # "" means all local interfaces

print("Waiting for a message on UDP port 4444 ...")

data, addr = sock.recvfrom(256)  # Receive up to 256 bytes
message = data.decode('utf-8')  # Decode bytes to string

print(f"Received '{message}' from {addr}")
