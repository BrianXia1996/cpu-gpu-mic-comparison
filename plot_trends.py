"""Rebuild the hardware trend figures and their numerical data."""
from __future__ import annotations

import argparse
import csv
from datetime import date
from math import ceil, floor, inf, isfinite, log10
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.dates as mdates
import matplotlib.pyplot as plt
from matplotlib.lines import Line2D
from matplotlib.path import Path as PlotPath
from matplotlib.font_manager import FontProperties
from matplotlib.ticker import (
    FixedLocator, FuncFormatter, LogFormatterMathtext, LogFormatterSciNotation, LogLocator, MaxNLocator,
    NullFormatter,
)
from matplotlib.transforms import Bbox

ROOT = Path(__file__).resolve().parent
SERIES = {
    "amd-cpu": ("AMD EPYC", "#a74c27", "o", "--"),
    "intel-cpu": ("Intel Xeon", "#24618d", "s", "--"),
    "amd-hpc": ("AMD Instinct", "#a74c27", "D", "-"),
    "nvidia-hpc": ("NVIDIA Tesla / data center GPU", "#377649", "v", "-"),
}
ARCHIVE_SERIES = {"amd-graphics", "intel-graphics", "nvidia-graphics", "intel-mic", "nvidia-cpu", "intel-hpc"}
ARCHIVE_DEVICES = {"opteron-6174", "w5590", "s9150", "c1060"}
STANDARD = ("FP64", "FP32")
REDUCED = ("TF32", "FP16", "BF16", "FP8")
ARCHIVE_PRECISIONS = ("NVFP4", "MXFP4")
FORMATS = STANDARD + REDUCED + ARCHIVE_PRECISIONS
PEAK = "peak_tflops"
DRAM = "memory_flop_per_byte"
POWER = "peak_gflops_per_w"
CACHE = "llc_flop_per_byte"
METRICS = {
    PEAK: ("peak", "Peak performance (TFLOPS)"),
    DRAM: ("flop-per-byte", "FLOP per byte"),
    POWER: ("performance-per-watt", "Peak performance per watt (GFLOPS per W)"),
}

plt.rcParams.update({
    "font.family": "serif",
    "font.serif": ["STIXGeneral"],
    "mathtext.fontset": "stix",
    "font.size": 9,
    "axes.labelsize": 9,
    "axes.titlesize": 10,
    "axes.titleweight": "semibold",
    "axes.spines.top": False,
    "axes.spines.right": False,
    "axes.edgecolor": "#676d73",
    "axes.linewidth": 0.6,
    "xtick.labelsize": 8,
    "ytick.labelsize": 8,
    "xtick.color": "#263039",
    "ytick.color": "#263039",
    "text.color": "#172028",
    "axes.labelcolor": "#172028",
    "legend.fontsize": 8,
    "pdf.fonttype": 42,
    "ps.fonttype": 42,
    "savefig.dpi": 400,
})


def read_table(directory, name):
    with (directory / name).open(newline="", encoding="utf-8-sig") as stream:
        yield from csv.DictReader(stream)


def require(condition, message):
    if not condition:
        raise ValueError(message)


def positive(row, column):
    value = row[column]
    if value == "":
        return None
    number = float(value)
    require(isfinite(number) and number > 0, f"{column} must be positive: {row}")
    return number


def load_data(directory):
    sources = {}
    for row in read_table(directory, "sources.csv"):
        key = row["source_id"]
        require(key and key not in sources, f"Invalid or duplicate source ID: {key}")
        require(row["url"].startswith("https://"), f"Missing source URL: {key}")
        sources[key] = row["url"]

    devices = {}
    for row in read_table(directory, "devices.csv"):
        key = row["id"]
        require(key and key not in devices, f"Invalid or duplicate device ID: {key}")
        require(row["series"] in SERIES or row["series"] in ARCHIVE_SERIES, f"{key}: unknown hardware series")
        month = row["launch_month"]
        launch = date.fromisoformat(month + "-01")
        require(launch.isoformat()[:7] == month, f"{key}: expected YYYY-MM")
        require(all(s in sources for s in row["sources"].split(";")), f"{key}: unknown source")
        row["launch"] = launch
        row["plot"] = row["series"] in SERIES and key not in ARCHIVE_DEVICES
        for column in ("memory_gb_s", "design_power_w", "cpu_cores", "cpu_base_ghz"):
            row[column] = positive(row, column)
        require(bool(row["power_basis"]) == bool(row["design_power_w"]), f"{key}: power basis mismatch")
        row["rates"] = {
            precision: (positive(row, precision.lower() + "_tflops"),
                        "vector" if precision in STANDARD else "matrix")
            for precision in FORMATS if precision not in {"FP16", "BF16"}
        }
        for precision in ("FP16", "BF16"):
            matrix = positive(row, precision.lower() + "_matrix_tflops")
            vector = positive(row, precision.lower() + "_vector_tflops")
            row["rates"][precision] = (matrix, "matrix") if matrix else (vector, "vector")
        devices[key] = row

    cache = {}
    for row in read_table(directory, "cache.csv"):
        key = row["device_id"]
        require(key in devices and key not in cache, f"Invalid or duplicate cache device: {key}")
        require(row["source_id"] in sources, f"{key}: unknown cache source")
        require(row["basis"] in {"measured", "specified"}, f"{key}: unknown bandwidth basis")
        require(row["level"] and row["method"], f"{key}: missing cache details")
        row["capacity_mib"] = positive(row, "capacity_mib")
        row["bandwidth_gb_s"] = positive(row, "bandwidth_gb_s")
        require(row["bandwidth_gb_s"] is not None, f"{key}: missing cache bandwidth")
        cache[key] = row

    require(devices, "Device table is empty")
    return sorted(devices.values(), key=lambda row: (row["launch"], row["id"])), cache


def divide(numerator, denominator):
    return numerator / denominator if denominator is not None else None


def derive(devices, cache):
    data = {}
    for device in devices:
        llc = cache.get(device["id"], {})
        for precision, (tflops, engine) in device["rates"].items():
            if tflops is not None:
                gflops = 1000 * tflops
                data[device["id"], precision] = {
                    "engine": engine,
                    "plotted": device["plot"] and (
                        precision in STANDARD or (precision in REDUCED and engine == "matrix")
                    ),
                    PEAK: tflops,
                    DRAM: divide(gflops, device["memory_gb_s"]),
                    POWER: divide(gflops, device["design_power_w"]),
                    CACHE: divide(gflops, llc.get("bandwidth_gb_s")),
                }
    return data


def export_data(out, devices, cache, data):
    fields = (
        "device_id", "model", "series", "plotted", "launch_month", "precision", "engine",
        PEAK, "memory_kind", "memory_gb_s", DRAM, "design_power_w", "power_basis", POWER,
        "llc_level", "llc_capacity_mib", "llc_bandwidth_gb_s", "llc_bandwidth_basis",
        "llc_source", CACHE, "device_sources",
    )
    with (out / "figure-data.csv").open("w", newline="", encoding="utf-8") as stream:
        writer = csv.DictWriter(stream, fieldnames=fields)
        writer.writeheader()
        for device in devices:
            key = device["id"]
            llc = cache.get(key, {})
            for precision in FORMATS:
                values = data.get((key, precision))
                if values is None:
                    continue
                values = {k: f"{v:.8g}" if isinstance(v, float) else v for k, v in values.items()}
                writer.writerow({
                    **values, "device_id": key, "model": device["model"], "series": device["series"],
                    "launch_month": device["launch_month"], "precision": precision,
                    "memory_kind": device["memory_kind"], "memory_gb_s": device["memory_gb_s"],
                    "design_power_w": device["design_power_w"], "power_basis": device["power_basis"],
                    "llc_level": llc.get("level"), "llc_capacity_mib": llc.get("capacity_mib"),
                    "llc_bandwidth_gb_s": llc.get("bandwidth_gb_s"),
                    "llc_bandwidth_basis": llc.get("basis"), "llc_source": llc.get("source_id"),
                    "device_sources": device["sources"],
                })


def log_ticks(ax, values, *, dense=False):
    lower = log10(min(values))
    upper = log10(max(values))
    padding = max(0.03, (upper - lower) * 0.08)
    axis_lower = lower - padding
    axis_upper = upper + 1.9 * padding
    limits = (10 ** axis_lower, 10 ** axis_upper)
    ax.set_yscale("log")
    ax.set_ylim(limits)
    axis = ax.yaxis
    axis.set_major_locator(LogLocator(base=10, numticks=8))
    axis.set_major_formatter(LogFormatterMathtext(base=10))
    decades = range(floor(axis_lower), ceil(axis_upper) + 1)
    decade_tick_count = sum(axis_lower <= decade <= axis_upper for decade in decades)
    if dense or decade_tick_count < 2:
        ticks = [10 ** decade * multiple for decade in decades for multiple in (1, 2, 5)
                 if axis_lower <= log10(10 ** decade * multiple) <= axis_upper]
        if len(ticks) < 3:
            # Choose round values for a narrow range. The y-axis still places them logarithmically.
            round_ticks = MaxNLocator(nbins=4, steps=(1, 2, 5, 10)).tick_values(*limits)
            ticks = [tick for tick in round_ticks if limits[0] <= tick <= limits[1]]
        if len(ticks) >= 2:
            axis.set_major_locator(FixedLocator(ticks))
            formatter = FuncFormatter(lambda value, _: f"{value:g}")
            if max(ticks) >= 1e4:
                formatter = LogFormatterSciNotation(base=10, minor_thresholds=(inf, inf))
            axis.set_major_formatter(formatter)
    axis.set_minor_locator(LogLocator(base=10, subs=range(2, 10), numticks=40))
    axis.set_minor_formatter(NullFormatter())


def legend(fig, active):
    handles = [Line2D([], [], color=color, marker=marker, linestyle=linestyle,
                      label=label, linewidth=1, markersize=4.4)
               for key, (label, color, marker, linestyle) in SERIES.items() if key in active]
    fig.legend(handles=handles, loc="lower center", bbox_to_anchor=(0.53, 0.08 / fig.get_figheight()),
               ncols=min(3, len(handles)), handlelength=2.2,
               columnspacing=1.7, frameon=False)


def ordered_label_centers(targets, half_widths, left_edge, right_edge, spacing):
    """Keep both edges of the labels in date order and balance horizontal shifts."""
    gaps = [max(spacing, abs(a - b) + spacing / 7)
            for a, b in zip(half_widths, half_widths[1:])]
    before = [0, *gaps]
    after = [*gaps, 0]
    lower = []
    for width, gap in zip(half_widths, before):
        start = lower[-1] + gap if lower else left_edge
        lower.append(max(left_edge + width, start))
    upper = []
    for width, gap in zip(reversed(half_widths), reversed(after)):
        end = upper[-1] - gap if upper else right_edge
        upper.append(min(right_edge - width, end))
    upper.reverse()

    require(all(lo <= hi for lo, hi in zip(lower, upper)),
            "Plot is too narrow for chronological model labels")
    forward = []
    for target, lo, hi, gap in zip(targets, lower, upper, before):
        start = forward[-1] + gap if forward else lo
        forward.append(max(lo, start, min(hi, target)))
    backward = []
    for target, lo, hi, gap in reversed(list(zip(targets, lower, upper, after))):
        end = backward[-1] - gap if backward else hi
        backward.append(min(hi, end, max(lo, target)))

    return [(a + b) / 2 for a, b in zip(forward, reversed(backward))]


def annotate_points(ax, observations, traces, renderer):
    """Anchor model labels from oldest to newest and pack them vertically."""
    if not observations:
        return
    observations = sorted(observations, key=lambda row: (row[0]["launch"], row[0]["id"]))
    font = FontProperties(size=7.6)
    scale = renderer.points_to_pixels(1)
    xy = [(mdates.date2num(device["launch"]), value) for device, value, _ in observations]
    positions = ax.transData.transform(xy)
    area = ax.bbox.padded(-2 * scale)
    half_widths = [
        renderer.get_text_width_height_descent(device["short_name"], font, ismath=False)[0] / 2
        + 1.7 * scale for device, _, _ in observations
    ]
    label_x = ordered_label_centers(positions[:, 0], half_widths, area.x0, area.x1, 10.5 * scale)
    half_height = 5.7 * scale
    marker_boxes = [Bbox.from_extents(x - 3 * scale, y - 3 * scale, x + 3 * scale, y + 3 * scale)
                    for x, y in positions]
    label_boxes = []
    connectors = []
    paths = [line.get_path().transformed(line.get_transform()) for line in traces]

    def placement_priority(i):
        y = positions[i, 1]
        edge_distance = min(y - area.y0, area.y1 - y)
        neighbors = sum(abs(label_x[i] - px) < half_widths[i] + width
                        and abs(y - py) < 21 * scale
                        for px, py, width in zip(label_x, positions[:, 1], half_widths))
        return edge_distance >= 20 * scale, -neighbors

    # Prioritize points near the top and bottom, where text has fewer places to fit.
    for i in sorted(range(len(xy)), key=placement_priority):
        device, _, color = observations[i]
        x, y = positions[i]
        center = label_x[i]
        left = center - half_widths[i]
        right = center + half_widths[i]
        obstacles = [box for box in marker_boxes + label_boxes
                     if left < box.x1 and right > box.x0]
        lower, upper = area.y0 + half_height, area.y1 - half_height
        candidates = {lower, upper, y}
        for rise in range(8, 73, 4):
            candidates.update((y + rise * scale, y - rise * scale))
        for box in obstacles:
            # Include gaps between existing labels even when the regular offsets miss them.
            candidates.update((box.y0 - half_height - 0.4 * scale,
                               box.y1 + half_height + 0.4 * scale))
        best = None
        for cy in sorted(candidates):
            if not lower <= cy <= upper:
                continue
            box = Bbox.from_extents(left, cy - half_height, right, cy + half_height)
            if box.count_overlaps(obstacles):
                continue
            connector = PlotPath([(x, y), (center, cy)])
            crossings = sum(path.intersects_bbox(box, filled=False) for path in paths)
            blocked = sum(connector.intersects_bbox(b, filled=False) for b in label_boxes)
            blocked += sum(path.intersects_bbox(box, filled=False) for path in connectors)
            crossed_leaders = sum(connector.intersects_path(path, filled=False)
                                  for path in connectors)
            distance = abs(cy - y) / scale
            cost = distance ** 2 + 160 * crossings + 420 * blocked + 130 * crossed_leaders
            if best is None or cost < best[0]:
                best = (cost, cy, box, connector)
        require(best is not None, f"Cannot place the model label for {device['short_name']}")
        _, cy, box, connector = best
        label_boxes.append(box)
        connectors.append(connector)
        ax.annotate(device["short_name"], xy[i], xytext=((center - x) / scale, (cy - y) / scale),
                    textcoords="offset points", fontproperties=font, ha="center", va="center",
                    zorder=4, bbox={"boxstyle": "square,pad=0.10", "fc": "white", "ec": "none"},
                    arrowprops={"arrowstyle": "-", "color": color, "alpha": 0.62,
                                "linewidth": 0.5, "shrinkA": 0.6, "shrinkB": 2.5})


def trends(devices, panels, ylabel, *, linear=False, dense_y_ticks=False, share_y=False,
           shared_y_pair=None):
    rows = len(panels)
    height = 0.90 + rows * 2.18
    fig, axes = plt.subplots(rows, 1, figsize=(7.15, height), sharex=True, sharey=share_y)
    if shared_y_pair:
        axes_by_title = {title: ax for ax, (title, _) in zip(axes, panels)}
        first, second = shared_y_pair
        axes_by_title[second].sharey(axes_by_title[first])
    dates = [d["launch"] for d in devices if any(d["id"] in panel for _, panel in panels)]
    values = [value for _, points in panels for value in points.values()]
    if not values:
        raise ValueError(f"No observations for {ylabel}")
    active = set()
    first_year = min(dates).year
    last_year = max(dates).year
    interval = 2 if last_year - first_year > 12 else 1
    years = range(last_year - (last_year - first_year) // interval * interval,
                  last_year + 1, interval)
    ticks = mdates.date2num([date(year, 1, 1) for year in years])
    observations_by_row = []
    for ax, (title, points) in zip(axes, panels):
        ax.set_title(title, loc="left", pad=6)
        traces = []
        observations = []
        for key, (_, color, marker, linestyle) in SERIES.items():
            selected = [d for d in devices if d["series"] == key]
            observed = [(d, points[d["id"]]) for d in selected if d["id"] in points]
            if not observed:
                continue
            active.add(key)
            trace, = ax.plot([d["launch"] for d in selected],
                             [points.get(d["id"]) for d in selected],
                             color=color, linestyle=linestyle, linewidth=1.05, zorder=2)
            traces.append(trace)
            for device, value in observed:
                ax.plot(device["launch"], value, marker=marker, markersize=4.5,
                        markerfacecolor=color,
                        markeredgecolor=color, markeredgewidth=0.8, zorder=3)
                observations.append((device, value, color))
        ax.xaxis.set_major_locator(FixedLocator(ticks))
        ax.xaxis.set_major_formatter(mdates.DateFormatter("%Y"))
        ax.tick_params(axis="both", which="major", length=3, width=0.6)
        ax.tick_params(axis="x", labelbottom=True)
        ax.tick_params(axis="y", which="minor", length=1.8, width=0.5)
        ax.grid(axis="y", which="major", linewidth=0.55, color="#d8dcdf")
        ax.set_axisbelow(True)
        observations_by_row.append((ax, observations, traces))
    points_by_axis = {ax: points for ax, (_, points) in zip(axes, panels)}
    scaled_axes = set()
    for ax in axes:
        if ax in scaled_axes:
            continue
        group = ax.get_shared_y_axes().get_siblings(ax)
        panel_values = [value for member in group for value in points_by_axis[member].values()] or values
        scaled_axes.update(group)
        if linear:
            lower, upper = min(panel_values), max(panel_values)
            span = max(upper - lower, 0.1 * upper)
            ax.set_ylim(max(0, lower - 0.07 * span), upper + 0.14 * span)
        else:
            log_ticks(ax, panel_values, dense=dense_y_ticks)
    start = min(min(dates).toordinal() - 220, date(first_year, 1, 1).toordinal())
    end = max(dates).toordinal() + 480
    axes[0].set_xlim(date.fromordinal(start), date.fromordinal(end))
    fig.subplots_adjust(left=0.105, right=0.98, bottom=0.93 / height,
                        top=1 - 0.32 / height, hspace=0.28)
    fig.supylabel(ylabel, x=0.023, y=0.5 + 0.3 / height)
    fig.supxlabel("Launch year", x=0.55, y=0.49 / height)
    legend(fig, active)
    fig.canvas.draw()
    renderer = fig.canvas.get_renderer()
    for ax, observations, traces in observations_by_row:
        annotate_points(ax, observations, traces, renderer)
    return fig


def trend_panels(devices, data, metric, precisions, *, scale=1):
    panels = []
    for precision in precisions:
        points = {}
        for device in devices:
            row = data.get((device["id"], precision), {})
            if row.get("plotted") and row[metric] is not None:
                points[device["id"]] = scale * row[metric]
        panels.append((precision, points))
    return panels


def save(fig, out, name, formats):
    for fmt in formats:
        fig.savefig(out / f"{name}.{fmt}", facecolor="white")
    plt.close(fig)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output-dir", type=Path, default=ROOT / "build" / "paper",
                        help="directory for figures and figure-data.csv (default: build/paper)")
    for fmt, short in (("pdf", "-v"), ("png", "-b"), ("eps", "-e")):
        parser.add_argument(short, f"--{fmt}", action="append_const", const=fmt, dest="formats")
    args = parser.parse_args()
    devices, cache = load_data(ROOT / "data")
    data = derive(devices, cache)
    plotted_devices = [device for device in devices if device["plot"]]
    out = args.output_dir
    out.mkdir(parents=True, exist_ok=True)
    formats = tuple(dict.fromkeys(args.formats or ("pdf", "png")))

    for metric, (filename, label) in METRICS.items():
        for precisions, suffix in ((STANDARD, "fp64-fp32"), (REDUCED, "low-precision")):
            low_precision_peak = metric == PEAK and precisions == REDUCED
            scale = 1000 if low_precision_peak else 1
            panels = trend_panels(plotted_devices, data, metric, precisions, scale=scale)
            ylabel = "Peak matrix throughput (GFLOPS)" if low_precision_peak else label
            shared_pair = ("FP16", "BF16") if metric == DRAM and precisions == REDUCED else None
            fig = trends(plotted_devices, panels, ylabel, dense_y_ticks=metric == DRAM,
                         share_y=metric == PEAK, shared_y_pair=shared_pair)
            save(fig, out, f"{filename}-{suffix}", formats)

    for field, name, axis_label in (
        ("memory_gb_s", "memory-bandwidth", "Memory interface bandwidth (GB/s)"),
        ("design_power_w", "design-power", "Device design power (W)"),
    ):
        # Separate socket CPUs from accelerators to keep the auxiliary plots readable.
        panels = []
        for title, cpu in (("CPUs", True), ("Accelerators", False)):
            points = {d["id"]: d[field] for d in plotted_devices
                      if d[field] and (d["series"].endswith("-cpu") == cpu)}
            panels.append((title, points))
        fig = trends(plotted_devices, panels, axis_label, linear=field == "design_power_w",
                     share_y=field == "memory_gb_s")
        save(fig, out, name, formats)

    export_data(out, devices, cache, data)
    print(f"{len(plotted_devices)} devices plotted; {len(data)} precision records in the CSV")
    print(f"Figures ({', '.join(formats)}) and figure-data.csv written to {out.resolve()}")


if __name__ == "__main__":
    main()
