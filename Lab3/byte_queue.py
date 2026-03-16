from threading import Lock, Event, Semaphore
from collections import deque


class ByteQueue:
    """
    Thread-safe FIFO buffer for incoming packets.
    Capacity is specified in bytes (sum of lengths of stored packets).
    """

    def __init__(self, MAX_BYTES: int, nonempty: Semaphore):
        """
        :param MAX_BYTES: total byte capacity allowed in the queue.
        :param nonempty: the number of non-empty queues
        """
        self.MAX_BYTES = MAX_BYTES  # queue capacity, in bytes
        self.bytes = 0              # current backlog, in bytes
        self.q = deque()            # underlying (not-thread-safe) queue
        self.lock = Lock()          # locks for accessing `bytes`
        self.nonempty = nonempty    # the number of non-empty buffers

    def _item_size(self, item) -> int:
        if isinstance(item, bytes):
            return len(item)
        return int(item["packet_size_bytes"])

    def try_put(self, item):
        """
        If there is available space, put `item` in the queue and returns True.
        Otherwise, discard the packet and returns False.
        """
        item_size = self._item_size(item)
        with self.lock:
            if self.bytes + item_size > self.MAX_BYTES:
                return False
            self.bytes += item_size
            self.q.append(item)
            if len(self.q) == 1:
                self.nonempty.release()
            return True

    def get(self):
        """
        Return the first item from the queue,
        assuming there is at least one packet.
        """
        with self.lock:
            item = self.q.popleft()
            self.bytes -= self._item_size(item)
            if not self.q:
                # We pop the last packet, it is now empty
                self.nonempty.acquire(timeout=0.0)
            return item

    def peek(self) -> bytes | None:
        """
        The head of queue, or None if the queue is empty.
        The head of queue is not removed.
        """
        with self.lock:
            if self.q:
                return self.q[0]

    def backlog(self) -> int:
        """Total backlog, in bytes."""
        with self.lock:
            return self.bytes

    def is_empty(self) -> bool:
        """Boolean whether the queue is empty"""
        with self.lock:
            return not self.q
