from __future__ import annotations

from dataclasses import dataclass
from typing import Iterable


@dataclass
class MatchedPacket:
    sequence: int
    send_time_ms: float
    receive_time_ms: float
    packet_size_bits: int


@dataclass
class BacklogResult:
    max_backlog_bits: float
    timeline_ms: list[float]
    arrival_bits: list[float]
    departure_bits: list[float]
    backlog_bits: list[float]
    matched_sequences: list[int]
    missing_sequences: list[int]
    duplicate_sequences: list[int]
    unexpected_sequences: list[int]


@dataclass
class ServiceCurveEstimate:
    time_grid_ms: list[float]
    service_bits: list[float]


def build_matched_packets(
    send_timestamps_ms: dict[int, float],
    receive_timestamps_ms: dict[int, float],
    duplicate_counts: dict[int, int],
    packet_size_bits: int,
) -> tuple[list[MatchedPacket], list[int], list[int], list[int]]:
    matched_sequences = sorted(set(send_timestamps_ms) & set(receive_timestamps_ms))
    missing_sequences = sorted(set(send_timestamps_ms) - set(receive_timestamps_ms))
    duplicate_sequences = sorted(seq for seq, count in duplicate_counts.items() if count > 0)
    unexpected_sequences = sorted(set(receive_timestamps_ms) - set(send_timestamps_ms))

    matched_packets = [
        MatchedPacket(
            sequence=sequence,
            send_time_ms=send_timestamps_ms[sequence],
            receive_time_ms=receive_timestamps_ms[sequence],
            packet_size_bits=packet_size_bits,
        )
        for sequence in matched_sequences
    ]
    return matched_packets, missing_sequences, duplicate_sequences, unexpected_sequences


def compute_backlog(
    send_timestamps_ms: dict[int, float],
    receive_timestamps_ms: dict[int, float],
    duplicate_counts: dict[int, int],
    packet_size_bits: int,
) -> BacklogResult:
    matched_packets, missing_sequences, duplicate_sequences, unexpected_sequences = build_matched_packets(
        send_timestamps_ms=send_timestamps_ms,
        receive_timestamps_ms=receive_timestamps_ms,
        duplicate_counts=duplicate_counts,
        packet_size_bits=packet_size_bits,
    )

    events: list[tuple[float, int, int]] = []
    for packet in matched_packets:
        events.append((packet.send_time_ms, 0, packet.packet_size_bits))
        events.append((packet.receive_time_ms, 1, packet.packet_size_bits))
    events.sort(key=lambda item: (item[0], item[1]))

    timeline_ms: list[float] = [0.0]
    arrival_bits: list[float] = [0.0]
    departure_bits: list[float] = [0.0]
    backlog_bits: list[float] = [0.0]

    arrivals = 0.0
    departures = 0.0
    max_backlog_bits = 0.0
    for timestamp_ms, event_type, size_bits in events:
        if event_type == 0:
            arrivals += size_bits
        else:
            departures += size_bits

        backlog = arrivals - departures
        max_backlog_bits = max(max_backlog_bits, backlog)
        timeline_ms.append(timestamp_ms)
        arrival_bits.append(arrivals)
        departure_bits.append(departures)
        backlog_bits.append(backlog)

    return BacklogResult(
        max_backlog_bits=max_backlog_bits,
        timeline_ms=timeline_ms,
        arrival_bits=arrival_bits,
        departure_bits=departure_bits,
        backlog_bits=backlog_bits,
        matched_sequences=[packet.sequence for packet in matched_packets],
        missing_sequences=missing_sequences,
        duplicate_sequences=duplicate_sequences,
        unexpected_sequences=unexpected_sequences,
    )


def build_time_grid(max_time_ms: float, num_points: int = 500) -> list[float]:
    capped_max_time = max(max_time_ms, 1.0)
    if num_points <= 1:
        return [0.0, capped_max_time]
    step = capped_max_time / (num_points - 1)
    return [index * step for index in range(num_points)]


def estimate_service_curve(
    probing_rates_kbps: Iterable[float],
    backlogs_bits: Iterable[float],
    time_grid_ms: list[float],
) -> ServiceCurveEstimate:
    rates = list(probing_rates_kbps)
    backlogs = list(backlogs_bits)
    if len(rates) != len(backlogs):
        raise ValueError("The probing rate and backlog vectors must have the same length.")

    service_bits: list[float] = []
    for time_ms in time_grid_ms:
        support_values = [rate_kbps * time_ms - backlog_bits for rate_kbps, backlog_bits in zip(rates, backlogs)]
        service_bits.append(max(0.0, max(support_values)))
    return ServiceCurveEstimate(time_grid_ms=time_grid_ms, service_bits=service_bits)


def ideal_service_curve(
    time_grid_ms: list[float],
    burst_bits: float,
    rate_kbps: float,
    latency_ms: float,
) -> list[float]:
    ideal_bits: list[float] = []
    for time_ms in time_grid_ms:
        if time_ms <= latency_ms:
            ideal_bits.append(0.0)
        else:
            ideal_bits.append(burst_bits + rate_kbps * (time_ms - latency_ms))
    return ideal_bits


def estimate_service_parameters(
    time_grid_ms: list[float],
    service_bits: list[float],
    packet_size_bits: int,
) -> dict[str, float]:
    if not time_grid_ms or not service_bits or len(time_grid_ms) != len(service_bits):
        raise ValueError("A non-empty time grid and service curve are required.")

    max_service_bits = max(service_bits)
    if max_service_bits <= 0:
        return {"R_kbps": 0.0, "T_ms": 0.0, "b_bits": 0.0}

    activation_threshold_bits = max(packet_size_bits, 0.01 * max_service_bits)
    activation_index = next(
        (index for index, value in enumerate(service_bits) if value >= activation_threshold_bits),
        0,
    )
    latency_ms = time_grid_ms[activation_index]

    start_index = max(activation_index, int(0.7 * (len(time_grid_ms) - 1)))
    fit_times = time_grid_ms[start_index:]
    fit_values = service_bits[start_index:]

    if len(fit_times) < 2:
        slope_kbps = 0.0
        intercept_bits = service_bits[-1]
    else:
        mean_time = sum(fit_times) / len(fit_times)
        mean_value = sum(fit_values) / len(fit_values)
        numerator = sum((time_ms - mean_time) * (value - mean_value) for time_ms, value in zip(fit_times, fit_values))
        denominator = sum((time_ms - mean_time) ** 2 for time_ms in fit_times)
        slope_kbps = numerator / denominator if denominator else 0.0
        intercept_bits = mean_value - slope_kbps * mean_time

    burst_bits = max(0.0, slope_kbps * latency_ms + intercept_bits)
    return {"R_kbps": max(0.0, slope_kbps), "T_ms": max(0.0, latency_ms), "b_bits": burst_bits}
