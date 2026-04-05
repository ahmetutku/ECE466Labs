from __future__ import annotations

import argparse
from pathlib import Path

from analysis import estimate_service_parameters, ideal_service_curve
from estimator import (
    DEFAULT_PACKET_SIZE_BYTES,
    DEFAULT_PROBING_RATES_KBPS,
    DEFAULT_SERVER_PORT,
    DEFAULT_TRAIN_LENGTH,
    ProbeRun,
    resolve_python_command,
    run_probe_train,
    run_service_curve_estimation,
    save_bmax_csv,
    save_json,
    save_probe_run_csv,
    save_processed_probe_summary,
    save_service_curve_csv,
)
from plotting import plot_bmax_vs_rate, plot_part1_timestamps, plot_service_curves


LAB4_DIR = Path(__file__).resolve().parent
RESULTS_DIR = LAB4_DIR / "results"
LMAX_BYTES = 1480
LMAX_BITS = 11840
DEFAULT_TIME_GRID_POINTS = 500

KNOWN_BOXES = {
    1: {"name": "known_box1", "burst_bits": 2 * LMAX_BITS, "rate_kbps": 1000.0, "latency_ms": 10.0},
    2: {"name": "known_box2", "burst_bits": 20 * LMAX_BITS, "rate_kbps": 1000.0, "latency_ms": 100.0},
    3: {"name": "known_box3", "burst_bits": 2 * LMAX_BITS, "rate_kbps": 5000.0, "latency_ms": 20.0},
}

UNKNOWN_BOXES = {
    1: {"name": "unknown_box1", "script": "blackbox1.py"},
    2: {"name": "unknown_box2", "script": "blackbox2.py"},
    3: {"name": "unknown_box3", "script": "blackbox3.py"},
}


def parse_rates(rate_tokens: list[str] | None) -> list[float]:
    if not rate_tokens:
        return list(DEFAULT_PROBING_RATES_KBPS)
    rates: list[float] = []
    for token in rate_tokens:
        for item in token.split(","):
            stripped = item.strip()
            if stripped:
                rates.append(float(stripped))
    if not rates:
        raise ValueError("At least one probing rate must be provided.")
    return rates


def ensure_directory(path: Path) -> Path:
    path.mkdir(parents=True, exist_ok=True)
    return path


def known_blackbox_command(box_index: int, server_port: int) -> list[str]:
    config = KNOWN_BOXES[box_index]
    return resolve_python_command(
        "blackbox.py",
        server_port,
        str(config["burst_bits"]),
        str(config["rate_kbps"]),
        str(config["latency_ms"]),
    )


def unknown_blackbox_command(box_index: int, server_port: int) -> list[str]:
    config = UNKNOWN_BOXES[box_index]
    return resolve_python_command(config["script"], server_port)


def save_run_artifacts(output_dir: Path, probe_runs: list[ProbeRun], probing_rates_kbps: list[float], time_grid_ms: list[float], service_bits: list[float]):
    raw_dir = ensure_directory(output_dir / "raw")
    processed_dir = ensure_directory(output_dir / "processed")

    for probe_run in probe_runs:
        rate_tag = f"{probe_run.rate_kbps:g}".replace(".", "_")
        save_probe_run_csv(raw_dir / f"probe_{rate_tag}kbps.csv", probe_run)
        save_processed_probe_summary(processed_dir / f"probe_{rate_tag}kbps.json", probe_run)

    save_bmax_csv(processed_dir / "bmax_vs_rate.csv", probing_rates_kbps, probe_runs)
    save_service_curve_csv(processed_dir / "service_curve.csv", time_grid_ms, service_bits)


def run_part1(args: argparse.Namespace):
    output_dir = ensure_directory(RESULTS_DIR / "part1")
    blackbox_command = resolve_python_command(
        "blackbox.py",
        args.server_port,
        str(args.burst_bits),
        str(args.box_rate_kbps),
        str(args.delay_ms),
    )
    summaries = []
    for index, rate_kbps in enumerate(args.rates, start=1):
        probe_run = run_probe_train(
            packet_size_bytes=args.packet_size_bytes,
            train_length=args.train_length,
            rate_kbps=rate_kbps,
            server_port=args.server_port,
            client_port=args.client_port,
            blackbox_command=blackbox_command,
            working_directory=LAB4_DIR,
        )
        packet_indices = list(range(args.train_length))
        send_times = [probe_run.send_timestamps_ms.get(sequence) for sequence in packet_indices]
        receive_times = [probe_run.receive_timestamps_ms.get(sequence) for sequence in packet_indices]
        plot_part1_timestamps(
            packet_indices=packet_indices,
            send_times_ms=send_times,
            receive_times_ms=receive_times,
            title=f"Part 1 probe train at {rate_kbps:g} kbps",
            output_path=output_dir / f"part1_rate_{index}_{rate_kbps:g}kbps.png",
        )
        save_probe_run_csv(output_dir / f"part1_rate_{index}_{rate_kbps:g}kbps.csv", probe_run)
        summaries.append(
            {
                "probing_rate_kbps": rate_kbps,
                "matched_packets": len(probe_run.backlog.matched_sequences),
                "missing_packets": len(probe_run.backlog.missing_sequences),
                "plot_path": str(output_dir / f"part1_rate_{index}_{rate_kbps:g}kbps.png"),
            }
        )

    save_json(output_dir / "summary.json", {"part": 1, "runs": summaries})
    print("Part 1 completed.")
    print(f"Results saved in: {output_dir}")
    print(f"BlackBox command: {' '.join(blackbox_command)}")


def run_known_experiment(
    box_index: int,
    experiment_dir: Path,
    packet_size_bytes: int,
    train_length: int,
    rates: list[float],
    server_port: int,
    client_port: int,
):
    config = KNOWN_BOXES[box_index]
    estimate = run_service_curve_estimation(
        probing_rates_kbps=rates,
        packet_size_bytes=packet_size_bytes,
        train_length=train_length,
        blackbox_command=known_blackbox_command(box_index, server_port),
        server_port=server_port,
        client_port=client_port,
        working_directory=LAB4_DIR,
        time_grid_points=DEFAULT_TIME_GRID_POINTS,
    )
    save_run_artifacts(
        output_dir=experiment_dir,
        probe_runs=estimate.probe_runs,
        probing_rates_kbps=rates,
        time_grid_ms=estimate.time_grid_ms,
        service_bits=estimate.service_bits,
    )
    ideal_bits = ideal_service_curve(
        time_grid_ms=estimate.time_grid_ms,
        burst_bits=config["burst_bits"],
        rate_kbps=config["rate_kbps"],
        latency_ms=config["latency_ms"],
    )
    plot_service_curves(
        curves=[
            ("Estimated service curve", estimate.time_grid_ms, estimate.service_bits),
            ("Ideal service curve", estimate.time_grid_ms, ideal_bits),
        ],
        title=f"Estimated vs Ideal Service Curve for {config['name']}",
        output_path=experiment_dir / "estimated_vs_ideal.png",
    )
    plot_bmax_vs_rate(
        probing_rates_kbps=rates,
        backlog_bits=[probe_run.backlog.max_backlog_bits for probe_run in estimate.probe_runs],
        title=f"B_max(r) vs r for {config['name']}",
        output_path=experiment_dir / "bmax_vs_rate.png",
    )
    summary = {
        "box": config["name"],
        "packet_size_bytes": packet_size_bytes,
        "packet_size_bits": packet_size_bytes * 8,
        "train_length": train_length,
        "probing_rates_kbps": rates,
        "ideal_parameters": {
            "b_bits": config["burst_bits"],
            "R_kbps": config["rate_kbps"],
            "T_ms": config["latency_ms"],
        },
        "B_max_bits": {f"{probe_run.rate_kbps:g}": probe_run.backlog.max_backlog_bits for probe_run in estimate.probe_runs},
    }
    save_json(experiment_dir / "processed" / "summary.json", summary)
    return estimate, ideal_bits, summary


def run_unknown_experiment(
    box_index: int,
    experiment_dir: Path,
    packet_size_bytes: int,
    train_length: int,
    rates: list[float],
    server_port: int,
    client_port: int,
):
    config = UNKNOWN_BOXES[box_index]
    estimate = run_service_curve_estimation(
        probing_rates_kbps=rates,
        packet_size_bytes=packet_size_bytes,
        train_length=train_length,
        blackbox_command=unknown_blackbox_command(box_index, server_port),
        server_port=server_port,
        client_port=client_port,
        working_directory=LAB4_DIR,
        time_grid_points=DEFAULT_TIME_GRID_POINTS,
    )
    save_run_artifacts(
        output_dir=experiment_dir,
        probe_runs=estimate.probe_runs,
        probing_rates_kbps=rates,
        time_grid_ms=estimate.time_grid_ms,
        service_bits=estimate.service_bits,
    )
    estimated_parameters = estimate_service_parameters(
        time_grid_ms=estimate.time_grid_ms,
        service_bits=estimate.service_bits,
        packet_size_bits=packet_size_bytes * 8,
    )
    fitted_curve = ideal_service_curve(
        time_grid_ms=estimate.time_grid_ms,
        burst_bits=estimated_parameters["b_bits"],
        rate_kbps=estimated_parameters["R_kbps"],
        latency_ms=estimated_parameters["T_ms"],
    )
    plot_service_curves(
        curves=[
            ("Estimated service curve", estimate.time_grid_ms, estimate.service_bits),
            ("Fitted curve from estimated parameters", estimate.time_grid_ms, fitted_curve),
        ],
        title=f"Estimated Service Curve for {config['name']}",
        output_path=experiment_dir / "estimated_service_curve.png",
    )
    plot_bmax_vs_rate(
        probing_rates_kbps=rates,
        backlog_bits=[probe_run.backlog.max_backlog_bits for probe_run in estimate.probe_runs],
        title=f"B_max(r) vs r for {config['name']}",
        output_path=experiment_dir / "bmax_vs_rate.png",
    )
    summary = {
        "box": config["name"],
        "packet_size_bytes": packet_size_bytes,
        "packet_size_bits": packet_size_bytes * 8,
        "train_length": train_length,
        "probing_rates_kbps": rates,
        "estimated_parameters": estimated_parameters,
        "B_max_bits": {f"{probe_run.rate_kbps:g}": probe_run.backlog.max_backlog_bits for probe_run in estimate.probe_runs},
    }
    save_json(experiment_dir / "processed" / "summary.json", summary)
    return estimate, fitted_curve, summary


def run_experiment1(args: argparse.Namespace):
    target_boxes = list(KNOWN_BOXES) if args.box == "all" else [int(args.box)]
    for box_index in target_boxes:
        box_dir = ensure_directory(RESULTS_DIR / KNOWN_BOXES[box_index]["name"] / "experiment1")
        run_known_experiment(
            box_index=box_index,
            experiment_dir=box_dir,
            packet_size_bytes=args.packet_size_bytes,
            train_length=args.train_length,
            rates=args.rates,
            server_port=args.server_port,
            client_port=args.client_port,
        )
        print(f"Experiment 1 saved for {KNOWN_BOXES[box_index]['name']} in {box_dir}")


def run_experiment2(args: argparse.Namespace):
    if args.target_type == "known":
        name = KNOWN_BOXES[int(args.box)]["name"]
        box_root = ensure_directory(RESULTS_DIR / name / "experiment2")
        curves: list[tuple[str, list[float], list[float]]] = []
        for run_index in range(1, args.runs + 1):
            run_dir = ensure_directory(box_root / f"run_{run_index:02d}")
            estimate, ideal_bits, _ = run_known_experiment(
                box_index=int(args.box),
                experiment_dir=run_dir,
                packet_size_bytes=args.packet_size_bytes,
                train_length=args.train_length,
                rates=args.rates,
                server_port=args.server_port,
                client_port=args.client_port,
            )
            curves.append((f"Run {run_index}", estimate.time_grid_ms, estimate.service_bits))
        curves.append(("Ideal service curve", estimate.time_grid_ms, ideal_bits))
        plot_service_curves(
            curves=curves,
            title=f"Repeated Service Curve Estimates for {name}",
            output_path=box_root / "repeated_runs_overlay.png",
        )
        save_json(
            box_root / "overlay_summary.json",
            {
                "runs": args.runs,
                "box": name,
                "packet_size_bytes": args.packet_size_bytes,
                "train_length": args.train_length,
                "probing_rates_kbps": args.rates,
            },
        )
        print(f"Experiment 2 saved for {name} in {box_root}")
        return

    name = UNKNOWN_BOXES[int(args.box)]["name"]
    box_root = ensure_directory(RESULTS_DIR / name / "experiment2")
    curves = []
    for run_index in range(1, args.runs + 1):
        run_dir = ensure_directory(box_root / f"run_{run_index:02d}")
        estimate, _, _ = run_unknown_experiment(
            box_index=int(args.box),
            experiment_dir=run_dir,
            packet_size_bytes=args.packet_size_bytes,
            train_length=args.train_length,
            rates=args.rates,
            server_port=args.server_port,
            client_port=args.client_port,
        )
        curves.append((f"Run {run_index}", estimate.time_grid_ms, estimate.service_bits))
    plot_service_curves(
        curves=curves,
        title=f"Repeated Service Curve Estimates for {name}",
        output_path=box_root / "repeated_runs_overlay.png",
    )
    save_json(
        box_root / "overlay_summary.json",
        {
            "runs": args.runs,
            "box": name,
            "packet_size_bytes": args.packet_size_bytes,
            "train_length": args.train_length,
            "probing_rates_kbps": args.rates,
        },
    )
    print(f"Experiment 2 saved for {name} in {box_root}")


def run_experiment3(args: argparse.Namespace):
    box_index = int(args.box)
    name = KNOWN_BOXES[box_index]["name"]
    experiment_dir = ensure_directory(RESULTS_DIR / name / "experiment3")

    baseline_dir = ensure_directory(experiment_dir / "baseline")
    doubled_dir = ensure_directory(experiment_dir / "doubled_train")
    larger_packet_dir = ensure_directory(experiment_dir / "larger_packets")

    baseline_estimate, ideal_bits, _ = run_known_experiment(
        box_index=box_index,
        experiment_dir=baseline_dir,
        packet_size_bytes=args.packet_size_bytes,
        train_length=args.train_length,
        rates=args.rates,
        server_port=args.server_port,
        client_port=args.client_port,
    )
    doubled_estimate, _, _ = run_known_experiment(
        box_index=box_index,
        experiment_dir=doubled_dir,
        packet_size_bytes=args.packet_size_bytes,
        train_length=args.train_length * 2,
        rates=args.rates,
        server_port=args.server_port,
        client_port=args.client_port,
    )
    larger_packet_size = min(LMAX_BYTES, args.larger_packet_size_bytes)
    larger_packet_estimate, _, _ = run_known_experiment(
        box_index=box_index,
        experiment_dir=larger_packet_dir,
        packet_size_bytes=larger_packet_size,
        train_length=args.train_length,
        rates=args.rates,
        server_port=args.server_port,
        client_port=args.client_port,
    )

    plot_service_curves(
        curves=[
            ("Baseline estimate", baseline_estimate.time_grid_ms, baseline_estimate.service_bits),
            ("Doubled N estimate", doubled_estimate.time_grid_ms, doubled_estimate.service_bits),
            ("Larger packet estimate", larger_packet_estimate.time_grid_ms, larger_packet_estimate.service_bits),
            ("Ideal service curve", baseline_estimate.time_grid_ms, ideal_bits),
        ],
        title=f"Baseline vs Larger Trains for {name}",
        output_path=experiment_dir / "baseline_vs_larger_trains.png",
    )
    save_json(
        experiment_dir / "comparison_summary.json",
        {
            "box": name,
            "baseline_packet_size_bytes": args.packet_size_bytes,
            "baseline_train_length": args.train_length,
            "larger_packet_size_bytes": larger_packet_size,
            "doubled_train_length": args.train_length * 2,
            "probing_rates_kbps": args.rates,
        },
    )
    print(f"Experiment 3 saved for {name} in {experiment_dir}")


def run_experiment4(args: argparse.Namespace):
    target_boxes = list(UNKNOWN_BOXES) if args.box == "all" else [int(args.box)]
    for box_index in target_boxes:
        box_dir = ensure_directory(RESULTS_DIR / UNKNOWN_BOXES[box_index]["name"] / "experiment4")
        _, _, summary = run_unknown_experiment(
            box_index=box_index,
            experiment_dir=box_dir,
            packet_size_bytes=args.packet_size_bytes,
            train_length=args.train_length,
            rates=args.rates,
            server_port=args.server_port,
            client_port=args.client_port,
        )
        print(
            f"Experiment 4 saved for {UNKNOWN_BOXES[box_index]['name']} in {box_dir} "
            f"with estimated parameters {summary['estimated_parameters']}"
        )


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="ECE466 Lab 4 Part 1 and Part 2 runner")
    subparsers = parser.add_subparsers(dest="command")

    def add_common_probe_arguments(
        subparser: argparse.ArgumentParser,
        default_packet_size_bytes: int = DEFAULT_PACKET_SIZE_BYTES,
        default_train_length: int = DEFAULT_TRAIN_LENGTH,
        default_rates: list[float] | None = None,
    ):
        selected_rates = default_rates or DEFAULT_PROBING_RATES_KBPS
        subparser.add_argument("--packet-size-bytes", type=int, default=default_packet_size_bytes)
        subparser.add_argument("--train-length", type=int, default=default_train_length)
        subparser.add_argument("--rates", nargs="+", default=[str(rate) for rate in selected_rates])
        subparser.add_argument("--server-port", type=int, default=DEFAULT_SERVER_PORT)
        subparser.add_argument("--client-port", type=int, default=5556)

    part1 = subparsers.add_parser("part1", help="Run the original Part 1 timestamp experiment")
    add_common_probe_arguments(
        part1,
        default_packet_size_bytes=400,
        default_train_length=100,
        default_rates=[10.0, 1000.0, 10000.0],
    )
    part1.add_argument("--burst-bits", type=float, default=400.0)
    part1.add_argument("--box-rate-kbps", default="inf")
    part1.add_argument("--delay-ms", type=float, default=10.0)

    experiment1 = subparsers.add_parser("experiment1", help="Run the known BlackBox estimator experiment")
    add_common_probe_arguments(experiment1)
    experiment1.add_argument("--box", default="all", choices=["1", "2", "3", "all"])

    experiment2 = subparsers.add_parser("experiment2", help="Run repeated estimations with identical parameters")
    add_common_probe_arguments(experiment2)
    experiment2.add_argument("--target-type", choices=["known", "unknown"], default="known")
    experiment2.add_argument("--box", required=True, choices=["1", "2", "3"])
    experiment2.add_argument("--runs", type=int, default=3)

    experiment3 = subparsers.add_parser("experiment3", help="Compare baseline, doubled N, and larger packets")
    add_common_probe_arguments(experiment3)
    experiment3.add_argument("--box", required=True, choices=["1", "2", "3"])
    experiment3.add_argument("--larger-packet-size-bytes", type=int, default=min(LMAX_BYTES, DEFAULT_PACKET_SIZE_BYTES * 2))

    experiment4 = subparsers.add_parser("experiment4", help="Run the estimator on the unknown BlackBoxes")
    add_common_probe_arguments(experiment4)
    experiment4.add_argument("--box", default="all", choices=["1", "2", "3", "all"])

    return parser


def main():
    parser = build_parser()
    args = parser.parse_args()

    if args.command is None:
        args = parser.parse_args(["part1"])

    if hasattr(args, "rates"):
        args.rates = parse_rates(args.rates)

    if args.command == "part1":
        run_part1(args)
    elif args.command == "experiment1":
        run_experiment1(args)
    elif args.command == "experiment2":
        run_experiment2(args)
    elif args.command == "experiment3":
        run_experiment3(args)
    elif args.command == "experiment4":
        run_experiment4(args)
    else:
        parser.error(f"Unsupported command: {args.command}")


if __name__ == "__main__":
    main()
