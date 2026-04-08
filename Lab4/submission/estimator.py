from __future__ import annotations

import csv
import json
import socket
import struct
import subprocess
import sys
import threading
import time
from collections import defaultdict
from dataclasses import dataclass
from pathlib import Path

from analysis import BacklogResult, build_time_grid, compute_backlog, estimate_service_curve


DEFAULT_SERVER_PORT = 5555
DEFAULT_CLIENT_PORT = 5556
DEFAULT_PACKET_SIZE_BYTES = 700
DEFAULT_TRAIN_LENGTH = 200
DEFAULT_PROBING_RATES_KBPS = [250.0, 500.0, 750.0, 1000.0, 1500.0, 2000.0, 3000.0, 4000.0, 5000.0, 6000.0]
SOCKET_TIMEOUT_SECONDS = 1.0
BLACKBOX_STARTUP_DELAY_SECONDS = 0.15
RECEIVE_DRAIN_SECONDS = 0.2


@dataclass
class ProbeRun:
    rate_kbps: float
    packet_size_bytes: int
    train_length: int
    send_timestamps_ms: dict[int, float]
    receive_timestamps_ms: dict[int, float]
    duplicate_counts: dict[int, int]
    backlog: BacklogResult

    @property
    def packet_size_bits(self) -> int:
        return self.packet_size_bytes * 8

    def max_time_ms(self) -> float:
        candidates = [0.0]
        if self.send_timestamps_ms:
            candidates.append(max(self.send_timestamps_ms.values()))
        if self.receive_timestamps_ms:
            candidates.append(max(self.receive_timestamps_ms.values()))
        return max(candidates)


@dataclass
class ServiceCurveRun:
    probing_rates_kbps: list[float]
    probe_runs: list[ProbeRun]
    time_grid_ms: list[float]
    service_bits: list[float]


def to_byte_array(value: int) -> bytearray:
    result = bytearray(4)
    result[3] = (value >> (8 * 0)) & 0xFF
    result[2] = (value >> (8 * 1)) & 0xFF
    result[1] = (value >> (8 * 2)) & 0xFF
    result[0] = (value >> (8 * 3)) & 0xFF
    return result


def genpkt(size_bytes: int, sequence: int, client_port: int = DEFAULT_CLIENT_PORT) -> bytearray:
    packet = bytearray(size_bytes)
    packet[0:2] = to_byte_array(client_port)[2:4]
    packet[2:6] = to_byte_array(sequence)
    return packet


def sendpkt(sock: socket.socket, size_bytes: int, sequence: int, server_port: int, client_port: int) -> None:
    message = genpkt(size_bytes=size_bytes, sequence=sequence, client_port=client_port)
    sock.sendto(message, ("127.0.0.1", server_port))


def _transmit(
    sock: socket.socket,
    event: threading.Event,
    train_length: int,
    packet_size_bytes: int,
    rate_kbps: float,
    server_port: int,
    client_port: int,
    send_timestamps_ms: dict[int, float],
    start_ns: int,
):
    event.clear()
    packet_size_bits = packet_size_bytes * 8
    if rate_kbps <= 0:
        raise ValueError("Probing rate must be positive.")
    gap_ns = int(round((packet_size_bits / (rate_kbps * 1000.0)) * 1e9))

    next_send_ns = start_ns
    for sequence in range(train_length):
        while time.monotonic_ns() < next_send_ns:
            pass
        sendpkt(
            sock=sock,
            size_bytes=packet_size_bytes,
            sequence=sequence,
            server_port=server_port,
            client_port=client_port,
        )
        send_timestamps_ms[sequence] = (time.monotonic_ns() - start_ns) / 1e6
        next_send_ns += gap_ns

    event.set()


def _recv(
    sock: socket.socket,
    event: threading.Event,
    receive_timestamps_ms: dict[int, float],
    duplicate_counts: dict[int, int],
    start_ns: int,
):
    while True:
        try:
            data, _ = sock.recvfrom(65535)
        except socket.timeout:
            if event.is_set():
                break
            continue

        if len(data) < 6:
            continue

        sequence = struct.unpack(">I", data[2:6])[0]
        timestamp_ms = (time.monotonic_ns() - start_ns) / 1e6
        if sequence in receive_timestamps_ms:
            duplicate_counts[sequence] += 1
        else:
            receive_timestamps_ms[sequence] = timestamp_ms


def _launch_blackbox(command: list[str] | None, cwd: Path) -> subprocess.Popen[str] | None:
    if command is None:
        return None
    process = subprocess.Popen(command, cwd=cwd, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, text=True)
    time.sleep(BLACKBOX_STARTUP_DELAY_SECONDS)
    return process


def _stop_blackbox(process: subprocess.Popen[str] | None):
    if process is None:
        return
    process.terminate()
    try:
        process.wait(timeout=1.0)
    except subprocess.TimeoutExpired:
        process.kill()
        process.wait(timeout=1.0)


def run_probe_train(
    packet_size_bytes: int,
    train_length: int,
    rate_kbps: float,
    server_port: int = DEFAULT_SERVER_PORT,
    client_port: int = DEFAULT_CLIENT_PORT,
    blackbox_command: list[str] | None = None,
    working_directory: Path | None = None,
) -> ProbeRun:
    send_timestamps_ms: dict[int, float] = {}
    receive_timestamps_ms: dict[int, float] = {}
    duplicate_counts: defaultdict[int, int] = defaultdict(int)
    sender_done_event = threading.Event()

    cwd = working_directory or Path(__file__).resolve().parent
    blackbox_process = _launch_blackbox(blackbox_command, cwd=cwd)

    send_socket = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    recv_socket = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    recv_socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    if hasattr(socket, "SO_REUSEPORT"):
        try:
            recv_socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEPORT, 1)
        except OSError:
            pass
    recv_socket.bind(("", client_port))
    recv_socket.settimeout(SOCKET_TIMEOUT_SECONDS)
    start_ns = time.monotonic_ns()

    transmitter = threading.Thread(
        target=_transmit,
        args=(
            send_socket,
            sender_done_event,
            train_length,
            packet_size_bytes,
            rate_kbps,
            server_port,
            client_port,
            send_timestamps_ms,
            start_ns,
        ),
        daemon=True,
    )
    receiver = threading.Thread(
        target=_recv,
        args=(recv_socket, sender_done_event, receive_timestamps_ms, duplicate_counts, start_ns),
        daemon=True,
    )

    try:
        receiver.start()
        transmitter.start()
        transmitter.join()
        time.sleep(RECEIVE_DRAIN_SECONDS)
        receiver.join()
    finally:
        send_socket.close()
        recv_socket.close()
        _stop_blackbox(blackbox_process)

    backlog = compute_backlog(
        send_timestamps_ms=send_timestamps_ms,
        receive_timestamps_ms=receive_timestamps_ms,
        duplicate_counts=dict(duplicate_counts),
        packet_size_bits=packet_size_bytes * 8,
    )
    return ProbeRun(
        rate_kbps=rate_kbps,
        packet_size_bytes=packet_size_bytes,
        train_length=train_length,
        send_timestamps_ms=send_timestamps_ms,
        receive_timestamps_ms=receive_timestamps_ms,
        duplicate_counts=dict(duplicate_counts),
        backlog=backlog,
    )


def run_service_curve_estimation(
    probing_rates_kbps: list[float],
    packet_size_bytes: int,
    train_length: int,
    blackbox_command: list[str] | None,
    server_port: int = DEFAULT_SERVER_PORT,
    client_port: int = DEFAULT_CLIENT_PORT,
    working_directory: Path | None = None,
    time_grid_points: int = 500,
) -> ServiceCurveRun:
    probe_runs = [
        run_probe_train(
            packet_size_bytes=packet_size_bytes,
            train_length=train_length,
            rate_kbps=rate_kbps,
            server_port=server_port,
            client_port=client_port,
            blackbox_command=blackbox_command,
            working_directory=working_directory,
        )
        for rate_kbps in probing_rates_kbps
    ]

    max_time_ms = max((probe_run.max_time_ms() for probe_run in probe_runs), default=1.0)
    time_grid_ms = build_time_grid(max_time_ms * 1.1, num_points=time_grid_points)
    estimate = estimate_service_curve(
        probing_rates_kbps=probing_rates_kbps,
        backlogs_bits=[probe_run.backlog.max_backlog_bits for probe_run in probe_runs],
        time_grid_ms=time_grid_ms,
    )
    return ServiceCurveRun(
        probing_rates_kbps=probing_rates_kbps,
        probe_runs=probe_runs,
        time_grid_ms=estimate.time_grid_ms,
        service_bits=estimate.service_bits,
    )


def save_probe_run_csv(output_path: Path, probe_run: ProbeRun):
    output_path.parent.mkdir(parents=True, exist_ok=True)
    with output_path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.writer(handle)
        writer.writerow(
            [
                "sequence_number",
                "send_timestamp_ms",
                "receive_timestamp_ms",
                "duplicate_count",
                "matched",
            ]
        )
        for sequence in range(probe_run.train_length):
            send_time = probe_run.send_timestamps_ms.get(sequence)
            receive_time = probe_run.receive_timestamps_ms.get(sequence)
            duplicate_count = probe_run.duplicate_counts.get(sequence, 0)
            matched = sequence in probe_run.backlog.matched_sequences
            writer.writerow([sequence, send_time, receive_time, duplicate_count, matched])


def save_processed_probe_summary(output_path: Path, probe_run: ProbeRun):
    output_path.parent.mkdir(parents=True, exist_ok=True)
    payload = {
        "rate_kbps": probe_run.rate_kbps,
        "packet_size_bytes": probe_run.packet_size_bytes,
        "packet_size_bits": probe_run.packet_size_bits,
        "train_length": probe_run.train_length,
        "B_max_bits": probe_run.backlog.max_backlog_bits,
        "matched_packets": len(probe_run.backlog.matched_sequences),
        "missing_sequences": probe_run.backlog.missing_sequences,
        "duplicate_sequences": probe_run.backlog.duplicate_sequences,
        "unexpected_sequences": probe_run.backlog.unexpected_sequences,
        "timeline_ms": probe_run.backlog.timeline_ms,
        "arrival_bits": probe_run.backlog.arrival_bits,
        "departure_bits": probe_run.backlog.departure_bits,
        "backlog_bits": probe_run.backlog.backlog_bits,
    }
    output_path.write_text(json.dumps(payload, indent=2), encoding="utf-8")


def save_service_curve_csv(output_path: Path, time_grid_ms: list[float], service_bits: list[float]):
    output_path.parent.mkdir(parents=True, exist_ok=True)
    with output_path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.writer(handle)
        writer.writerow(["time_ms", "service_bits"])
        for time_ms, service in zip(time_grid_ms, service_bits):
            writer.writerow([time_ms, service])


def save_bmax_csv(output_path: Path, probing_rates_kbps: list[float], probe_runs: list[ProbeRun]):
    output_path.parent.mkdir(parents=True, exist_ok=True)
    with output_path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.writer(handle)
        writer.writerow(["rate_kbps", "B_max_bits", "matched_packets", "missing_packets", "duplicate_sequences"])
        for rate_kbps, probe_run in zip(probing_rates_kbps, probe_runs):
            writer.writerow(
                [
                    rate_kbps,
                    probe_run.backlog.max_backlog_bits,
                    len(probe_run.backlog.matched_sequences),
                    len(probe_run.backlog.missing_sequences),
                    len(probe_run.backlog.duplicate_sequences),
                ]
            )


def save_json(output_path: Path, payload: dict):
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(json.dumps(payload, indent=2), encoding="utf-8")


def resolve_python_command(script_name: str, inport: int = DEFAULT_SERVER_PORT, *extra_args: str) -> list[str]:
    script_path = Path(__file__).resolve().parent / script_name
    return [sys.executable, str(script_path), f"--inport={inport}", *extra_args]
