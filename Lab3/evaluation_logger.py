import csv
import threading
import time


class EvaluationLogger:
    def __init__(self, path: str):
        self.path = path
        self.lock = threading.Lock()
        self.start_ns = time.monotonic_ns()
        self.next_seq = 0
        self.next_flush = 0
        self.cum_drops = 0
        self.records = {}
        self.csv_file = open(path, "w", newline="")
        self.writer = csv.writer(self.csv_file)
        self.writer.writerow([
            "arrival_time_s",
            "packet_size_bytes",
            "backlog_bytes",
            "departure_time_s",
            "waiting_time_s",
            "dropped",
            "cum_drops",
        ])
        self.csv_file.flush()

    def log_arrival(self, packet_size: int, backlog_bytes: int, dropped: bool):
        with self.lock:
            seq = self.next_seq
            self.next_seq += 1
            arrival_ns = time.monotonic_ns()
            record = {
                "seq": seq,
                "arrival_ns": arrival_ns,
                "packet_size_bytes": packet_size,
                "backlog_bytes": backlog_bytes,
                "departure_time_s": "",
                "waiting_time_s": "",
                "dropped": int(dropped),
            }
            if dropped:
                self.cum_drops += 1
                record["cum_drops"] = self.cum_drops
                record["complete"] = True
            else:
                record["cum_drops"] = self.cum_drops
                record["complete"] = False
            self.records[seq] = record
            self._flush_ready()
            return record

    def log_departure(self, record, departure_ns: int):
        with self.lock:
            stored = self.records[record["seq"]]
            stored["departure_time_s"] = self._to_seconds(departure_ns)
            stored["waiting_time_s"] = (departure_ns - stored["arrival_ns"]) / 1e9
            stored["complete"] = True
            self._flush_ready()

    def log_drop(self, record):
        with self.lock:
            stored = self.records[record["seq"]]
            self.cum_drops += 1
            stored["dropped"] = 1
            stored["cum_drops"] = self.cum_drops
            stored["complete"] = True
            self._flush_ready()

    def _flush_ready(self):
        while self.next_flush in self.records:
            record = self.records[self.next_flush]
            if not record["complete"]:
                break
            self.writer.writerow([
                self._to_seconds(record["arrival_ns"]),
                record["packet_size_bytes"],
                record["backlog_bytes"],
                record["departure_time_s"],
                record["waiting_time_s"],
                record["dropped"],
                record["cum_drops"],
            ])
            self.csv_file.flush()
            del self.records[self.next_flush]
            self.next_flush += 1

    def _to_seconds(self, timestamp_ns: int) -> float:
        return (timestamp_ns - self.start_ns) / 1e9
