import threading


class PriorityStats:
    def __init__(self):
        self.lock = threading.Lock()
        self.classified_high = 0
        self.classified_low = 0
        self.dropped_high = 0
        self.dropped_low = 0
        self.transmitted_high = 0
        self.transmitted_low = 0

    def note_classified(self, is_high: bool):
        with self.lock:
            if is_high:
                self.classified_high += 1
            else:
                self.classified_low += 1

    def note_dropped(self, is_high: bool):
        with self.lock:
            if is_high:
                self.dropped_high += 1
            else:
                self.dropped_low += 1

    def note_transmitted(self, is_high: bool):
        with self.lock:
            if is_high:
                self.transmitted_high += 1
            else:
                self.transmitted_low += 1

    def summary_lines(self):
        with self.lock:
            return [
                f"classified_high={self.classified_high}",
                f"classified_low={self.classified_low}",
                f"dropped_high={self.dropped_high}",
                f"dropped_low={self.dropped_low}",
                f"transmitted_high={self.transmitted_high}",
                f"transmitted_low={self.transmitted_low}",
            ]
