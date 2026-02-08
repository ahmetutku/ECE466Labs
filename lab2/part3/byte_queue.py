from threading import Lock, Event
from collections import deque


class ByteQueue:
    """
    Thread-safe FIFO buffer for incoming packets.
    Capacity is specified in bytes (sum of lengths of stored packets).
    """

    def __init__(self, MAX_BYTES: int):
        """:param MAX_BYTES: total byte capacity allowed in the queue."""
        self.MAX_BYTES = MAX_BYTES  # queue capacity, in bytes
        self.bytes = 0              # current backlog, in bytes
        self.q = deque()            # underlying (not-thread-safe) queue
        self.lock = Lock()          # locks for accessing `bytes`
        self.nonempty = Event()     # notify when the packet is non-empty

    def try_put(self, data: bytes):
        """
        If there is available space, put `data` in the queue and returns True.
        Otherwise, discard the packet and returns False.
        """
        with self.lock:
            if self.bytes + len(data) > self.MAX_BYTES:
                return False
            self.bytes += len(data)
            self.q.append(data)
            self.nonempty.set()
            return True

    def get(self):
        """
        Return the first packet from the queue,
        assuming there is at least one packet.
        """
        with self.lock:
            data: bytes = self.q.popleft()
            self.bytes -= len(data)
            if not self.q:
                # We pop the last packet, clear the non-empty flag
                self.nonempty.clear()
            return data

    def wait(self, timeout: float | None = None):
        """Block until a packet becomes available."""
        self.nonempty.wait(timeout)

    def peek(self):
        """
        The head of queue, or None if the queue is empty.
        The head of queue is not removed.
        """
        with self.lock:
            if self.q:
                return self.q[0]

    def backlog(self):
        """Total backlog, in bytes."""
        with self.lock:
            return self.bytes

    def is_empty(self):
        """Boolean whether the queue is empty"""
        with self.lock:
            return not self.q
