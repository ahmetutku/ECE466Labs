import numpy as np
import matplotlib.pyplot as plt


# ---------- helpers ----------
def cumtime_from_deltas_us(deltas_us):
    """Convert inter-arrival deltas (us) to cumulative time (s)."""
    return np.cumsum(deltas_us) / 1e6

def cumbytes(sizes):
    return np.cumsum(sizes)

def load_tb_log(path):
    """
    Token bucket log format:
      delta_us  pkt_len  backlog_bytes  tokens
    """
    delta_us = []
    sizes = []
    backlog = []
    tokens = []
    with open(path, "r") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            du, sz, b, tok = line.split()
            delta_us.append(float(du))
            sizes.append(int(float(sz)))
            backlog.append(float(b))
            tokens.append(float(tok))
    delta_us = np.array(delta_us)
    sizes = np.array(sizes)
    backlog = np.array(backlog)
    tokens = np.array(tokens)
    t = cumtime_from_deltas_us(delta_us)
    return t, sizes, backlog, tokens

def load_sink_log(path):
    """
    Sink log format (your Receiver):
      header line
      delta_us  pkt_len
    """
    delta_us = []
    sizes = []
    with open(path, "r") as f:
        first = True
        for line in f:
            line = line.strip()
            if not line:
                continue
            if first and ("delta" in line or "elapsed" in line):
                first = False
                continue
            first = False
            du, sz = line.split()
            delta_us.append(float(du))
            sizes.append(int(float(sz)))
    delta_us = np.array(delta_us)
    sizes = np.array(sizes)
    t = cumtime_from_deltas_us(delta_us)
    return t, sizes

def load_video_trace(path, limit=None, max_dgram=1400):
    """
    movietrace.data commonly: seq  time_ms  frameType  size_bytes ...
    For plotting, we convert each frame into UDP chunks of size max_dgram,
    because that's what your Sender actually sends.
    """
    rows = []
    with open(path, "r") as f:
        for line in f:
            line = line.strip()
            if not line or line.startswith("#"):
                continue
            parts = line.split()
            if len(parts) < 4:
                continue
            t_ms = float(parts[1])
            frame_bytes = int(parts[3])

            # split into chunks (same timestamp)
            remaining = frame_bytes
            while remaining > 0:
                chunk = min(remaining, max_dgram)
                rows.append((t_ms, chunk))
                remaining -= chunk

            if limit is not None and len(rows) >= limit:
                break

    rows.sort(key=lambda x: x[0])
    t = np.array([r[0] for r in rows]) / 1000.0
    sz = np.array([r[1] for r in rows])
    return t, sz

def load_eth_trace(path, limit=None, max_dgram=1400):
    """
    BC-pAug89.TL format (confirmed): time_sec  size_bytes
    For plotting, we split packets into chunks of max_dgram like Sender does.
    """
    rows = []
    with open(path, "r") as f:
        for line in f:
            line = line.strip()
            if not line or line.startswith("#"):
                continue
            parts = line.split()
            if len(parts) < 2:
                continue
            t_s = float(parts[0])
            pkt_bytes = int(parts[1])

            remaining = pkt_bytes
            while remaining > 0:
                chunk = min(remaining, max_dgram)
                rows.append((t_s, chunk))
                remaining -= chunk

            if limit is not None and len(rows) >= limit:
                break

    rows.sort(key=lambda x: x[0])
    t = np.array([r[0] for r in rows])  # already seconds
    sz = np.array([r[1] for r in rows])
    return t, sz


def plot_set(tag, in_t, in_sz, tb_log_path, sink_log_path, out_prefix):
    tb_t, tb_sz, tb_backlog, tb_tokens = load_tb_log(tb_log_path)
    out_t, out_sz = load_sink_log(sink_log_path)

    # cumulative bytes
    plt.figure()
    plt.plot(in_t, cumbytes(in_sz), label=f"Input ({tag})")
    plt.plot(tb_t, cumbytes(tb_sz), label="Arrivals at Token Bucket")
    plt.plot(out_t, cumbytes(out_sz), label="Output (Sink)")
    plt.xlabel("Time (s)")
    plt.ylabel("Cumulative bytes")
    plt.legend()
    plt.tight_layout()
    plt.savefig(f"{out_prefix}_cumbytes.png", dpi=200)

    # tokens
    plt.figure()
    plt.plot(tb_t, tb_tokens)
    plt.xlabel("Time (s)")
    plt.ylabel("Tokens (bytes)")
    plt.tight_layout()
    plt.savefig(f"{out_prefix}_tokens.png", dpi=200)

    # backlog
    plt.figure()
    plt.plot(tb_t, tb_backlog)
    plt.xlabel("Time (s)")
    plt.ylabel("Backlog (bytes)")
    plt.tight_layout()
    plt.savefig(f"{out_prefix}_backlog.png", dpi=200)


if __name__ == "__main__":
    # Match your run settings
    LIMIT = 1000
    MAX_DGRAM = 1400

    # --- VIDEO (Part 3-c) ---
    # Input trace is in part3/, logs are arrivals_video.log (part3) and sink_video.log (part2)
    video_in_t, video_in_sz = load_video_trace("movietrace.data", limit=LIMIT, max_dgram=MAX_DGRAM)
    plot_set(
        tag="Video trace",
        in_t=video_in_t,
        in_sz=video_in_sz,
        tb_log_path="arrivals_video.log",
        sink_log_path="../part2/sink_video.log",
        out_prefix="p3c_video"
    )

    # --- ETHERNET (Part 3-c) ---
    eth_in_t, eth_in_sz = load_eth_trace("BC-pAug89.TL", limit=LIMIT, max_dgram=MAX_DGRAM)
    plot_set(
        tag="Ethernet trace",
        in_t=eth_in_t,
        in_sz=eth_in_sz,
        tb_log_path="arrivals_eth.log",
        sink_log_path="../part2/sink_eth.log",
        out_prefix="p3c_eth"
    )

    print("Saved: p3c_video_{cumbytes,tokens,backlog}.png and p3c_eth_{cumbytes,tokens,backlog}.png")