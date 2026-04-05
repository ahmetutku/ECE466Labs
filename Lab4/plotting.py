from __future__ import annotations

from pathlib import Path

import matplotlib.pyplot as plt


def _service_scale(values: list[float]) -> tuple[float, str]:
    max_value = max((abs(value) for value in values), default=0.0)
    if max_value >= 1e4:
        return 1000.0, "Kbits"
    return 1.0, "bits"


def _prepare_axes(title: str, xlabel: str, ylabel: str):
    fig, ax = plt.subplots(figsize=(10, 6))
    ax.set_title(title)
    ax.set_xlabel(xlabel)
    ax.set_ylabel(ylabel)
    ax.grid(True, linestyle="--", linewidth=0.6, alpha=0.7)
    return fig, ax


def plot_part1_timestamps(
    packet_indices: list[int],
    send_times_ms: list[float | None],
    receive_times_ms: list[float | None],
    title: str,
    output_path: Path,
):
    fig, ax = _prepare_axes(title=title, xlabel="Packet sent/received", ylabel="Time (ms)")
    ax.plot(packet_indices, send_times_ms, label="Send timestamps", linewidth=1.6)
    ax.plot(packet_indices, receive_times_ms, label="Receive timestamps", linewidth=1.6)
    ax.legend()
    fig.tight_layout()
    fig.savefig(output_path, dpi=300)
    plt.close(fig)


def plot_service_curves(
    curves: list[tuple[str, list[float], list[float]]],
    title: str,
    output_path: Path,
):
    all_values = [value for _, _, curve in curves for value in curve]
    scale_factor, unit_label = _service_scale(all_values)
    fig, ax = _prepare_axes(title=title, xlabel="Time (ms)", ylabel=f"Service ({unit_label})")
    for label, time_grid_ms, values in curves:
        scaled_values = [value / scale_factor for value in values]
        ax.plot(time_grid_ms, scaled_values, label=label, linewidth=1.8)
    ax.legend()
    fig.tight_layout()
    fig.savefig(output_path, dpi=300)
    plt.close(fig)


def plot_bmax_vs_rate(
    probing_rates_kbps: list[float],
    backlog_bits: list[float],
    title: str,
    output_path: Path,
):
    scale_factor, unit_label = _service_scale(backlog_bits)
    scaled_backlogs = [value / scale_factor for value in backlog_bits]
    fig, ax = _prepare_axes(title=title, xlabel="Probing rate (kbps)", ylabel=f"Backlog ({unit_label})")
    ax.plot(probing_rates_kbps, scaled_backlogs, marker="o", linewidth=1.8)
    fig.tight_layout()
    fig.savefig(output_path, dpi=300)
    plt.close(fig)
