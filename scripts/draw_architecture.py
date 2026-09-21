#!/usr/bin/env python3
"""Draw the repository architecture diagram as a reproducible SVG asset."""

from __future__ import annotations

from html import escape
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "docs" / "architecture.svg"


def rect(x, y, w, h, fill, r=24, stroke="none", sw=0, extra=""):
    return f'<rect x="{x}" y="{y}" width="{w}" height="{h}" rx="{r}" fill="{fill}" stroke="{stroke}" stroke-width="{sw}" {extra}/>'


def text(x, y, value, cls, fill=None, anchor=None):
    attrs = f'class="{cls}"'
    if fill:
        attrs += f' fill="{fill}"'
    if anchor:
        attrs += f' text-anchor="{anchor}"'
    return f'<text x="{x}" y="{y}" {attrs}>{escape(value)}</text>'


def pill(x, y, w, label, bg, fg):
    return rect(x, y, w, 52, bg, 26) + text(x + w / 2, y + 34, label, "step", fg, "middle")


def step(x, y, w, label, bg, fg):
    return rect(x, y, w, 60, bg, 16) + text(x + w / 2, y + 38, label, "step", fg, "middle")


def workflow(x, number, title, subtitle, labels, accent, pale):
    out = [rect(x, 415, 640, 228, "#FFFFFF", 28, "#D7E2F0", 2, 'filter="url(#shadow)"')]
    out += [rect(x + 28, 443, 60, 60, accent, 18), text(x + 58, 484, number, "host-chip", "#FFFFFF", "middle")]
    out += [text(x + 112, 476, title, "card-title"), text(x + 112, 516, subtitle, "card-sub")]
    widths = [140, 140, 140, 128]
    for i, label in enumerate(labels):
        sx = x + 28 + sum(widths[:i]) + i * 12
        out += [step(sx, 539, widths[i], label, pale, accent)]
        if i < 3:
            out.append(f'<path d="M{sx + widths[i] + 2} 569 H{sx + widths[i] + 10}" stroke="{accent}" stroke-width="4" marker-end="url(#blueArrow)"/>')
    return "".join(out)


def source(x, title, subtitle, accent, gate=False):
    out = [rect(x, 1150, 440, 120, "#FFFFFF", 24, "#D4E0ED", 2, 'filter="url(#shadow)"')]
    out += [rect(x + 24, 1174, 10, 72, accent, 5), text(x + 56, 1197, title, "source-title"), text(x + 56, 1238, subtitle, "source-sub")]
    if gate:
        out += [rect(x + 294, 1171, 122, 36, "#FFF0E5", 18), text(x + 355, 1195, "USER GATE", "gate", "#C15919", "middle")]
    return "".join(out)


def main() -> int:
    parts = [
        '<svg xmlns="http://www.w3.org/2000/svg" width="2400" height="1350" viewBox="0 0 2400 1350" role="img" aria-labelledby="title desc">',
        '<title id="title">New Energy Research Agent architecture</title>',
        '<desc id="desc">Codex-first local scientific agent with three workflow modes, deterministic tools, evidence workspace, public data sources, and a user approval gate for remote compute.</desc>',
        '<defs><linearGradient id="bg" x1="0" y1="0" x2="1" y2="1"><stop stop-color="#F7FAFE"/><stop offset="1" stop-color="#EEF4FB"/></linearGradient><linearGradient id="host" x1="0" y1="0" x2="1" y2="0"><stop stop-color="#10233C"/><stop offset="1" stop-color="#183555"/></linearGradient><filter id="shadow"><feDropShadow dx="0" dy="10" stdDeviation="12" flood-color="#183555" flood-opacity=".14"/></filter><marker id="arrow" viewBox="0 0 12 12" refX="10" refY="6" markerWidth="10" markerHeight="10" orient="auto"><path d="M0 0L12 6L0 12z" fill="#8AA2BE"/></marker><marker id="blueArrow" viewBox="0 0 12 12" refX="10" refY="6" markerWidth="10" markerHeight="10" orient="auto"><path d="M0 0L12 6L0 12z" fill="#5A87C2"/></marker><style>.title{font:700 49px DejaVu Sans,Arial,sans-serif;fill:#10213A;letter-spacing:1px}.subtitle{font:400 25px DejaVu Sans,Arial,sans-serif;fill:#60728A}.eyebrow{font:700 21px DejaVu Sans,Arial,sans-serif;fill:#7DA7DC;letter-spacing:2px}.host-title{font:700 34px DejaVu Sans,Arial,sans-serif;fill:#fff}.host-chip{font:700 20px DejaVu Sans,Arial,sans-serif;fill:#DCEBFF}.card-title{font:700 31px DejaVu Sans,Arial,sans-serif;fill:#14243A}.card-sub{font:400 21px DejaVu Sans,Arial,sans-serif;fill:#5E7087}.step{font:700 20px DejaVu Sans,Arial,sans-serif}.section{font:700 25px DejaVu Sans,Arial,sans-serif;fill:#213754;letter-spacing:1px}.body{font:400 21px DejaVu Sans,Arial,sans-serif;fill:#65758A}.small{font:400 15px DejaVu Sans,Arial,sans-serif;fill:#6D7C8E}.artifact{font:700 20px DejaVu Sans,Arial,sans-serif;fill:#334961}.source-title{font:700 25px DejaVu Sans,Arial,sans-serif;fill:#263A52}.source-sub{font:400 18px DejaVu Sans,Arial,sans-serif;fill:#6B7A8D}.gate{font:700 15px DejaVu Sans,Arial,sans-serif}</style></defs>',
        '<rect width="2400" height="1350" fill="url(#bg)"/><circle cx="160" cy="35" r="410" fill="#DCEBFF" opacity=".33"/><circle cx="2260" cy="1290" r="440" fill="#D9F5EA" opacity=".27"/>',
        text(120, 104, "NEW ENERGY RESEARCH AGENT", "title"), text(120, 165, "Codex-first  ·  evidence-tracked  ·  reproducible materials research", "subtitle"),
        pill(1860, 67, 170, "LOCAL", "#E8F1FF", "#246BCE"), pill(2050, 67, 230, "MODEL-AGNOSTIC", "#E9F9F2", "#138A61"),
        rect(120, 205, 2160, 144, "url(#host)", 34, "none", 0, 'filter="url(#shadow)"'), text(160, 240, "HOST AGENT", "eyebrow"),
        text(160, 296, "Codex", "host-title"), text(304, 296, "/", "host-title", "#7187A4"), text(338, 296, "Claude Code", "host-title"), text(568, 296, "/", "host-title", "#7187A4"), text(602, 296, "compatible coding agents", "host-title"),
    ]
    for x, label, w in [(1390, "AGENTS.md", 180), (1595, "Commands", 180), (1800, "Skills", 180), (2005, "Specialist roles", 220)]:
        parts += [rect(x, 249, w, 60, "#1D385A", 16, "#335478", 2), text(x + w / 2, 287, label, "host-chip", "#DCEBFF", "middle")]
    parts += ['<path d="M1200 349V386M440 386H1960M440 386V415M1200 386V415M1960 386V415" fill="none" stroke="#84A2C7" stroke-width="7" marker-end="url(#arrow)"/>']
    parts += [workflow(120, "01", "Research Assistant", "Evidence before conclusions", ["Question", "Search", "Evidence", "Hypothesis"], "#246BCE", "#EAF2FF")]
    parts += [workflow(880, "02", "Data & Prediction", "Leakage-aware baselines", ["Contract", "Quality", "Split", "Evaluate"], "#7C4DDB", "#F1ECFF")]
    parts += [workflow(1640, "03", "Compute Orchestrator", "Approval before expensive work", ["Plan", "Review", "Approve", "Execute"], "#D56A25", "#FFF0E5")]
    parts += ['<path d="M440 643V680M1200 643V680M1960 643V680" stroke="#9BAFC6" stroke-width="6" marker-end="url(#arrow)"/>']
    parts += [rect(120, 680, 1650, 184, "#FFFFFF", 30, "#D7E2F0", 2, 'filter="url(#shadow)"'), text(160, 723, "DETERMINISTIC SCIENTIFIC EXECUTION", "section"), text(160, 763, "Python tools produce inspectable data, metrics and manifests", "body")]
    tool_data = [("Data quality", "missing · duplicate · leakage", "#EAF2FF", "#246BCE"), ("ML baseline", "group split · metrics", "#F1ECFF", "#7C4DDB"), ("Materials Project", "query · provenance · join", "#E9F9F2", "#138A61"), ("DFT parser", "energy · convergence", "#FFF0E5", "#D56A25")]
    for i, (name, detail, bg, fg) in enumerate(tool_data):
        x = 160 + i * 394
        parts += [rect(x, 801, 365, 46, bg, 13), f'<circle cx="{x + 24}" cy="824" r="7" fill="{fg}"/>', text(x + 42, 830, name, "artifact"), text(x + 154, 830, detail, "small")]
    parts += [rect(1810, 680, 470, 184, "#13283F", 30), text(1850, 723, "SAFETY RAILS", "section", "#8DB6E6")]
    for y, label in [(781, "Evidence states stay explicit"), (821, "User gate for SSH / GPU / cost"), (861, "Secrets remain outside Git")]:
        parts += [f'<circle cx="1857" cy="{y - 7}" r="7" fill="#38D19B"/>', text(1880, y, label, "body", "#ECF5FF")]
    parts += ['<path d="M1200 864V910" stroke="#8EA6C0" stroke-width="7" marker-end="url(#arrow)"/>', rect(120, 910, 2160, 170, "#EAF0F7", 32, "#CCD9E8", 2), text(160, 952, "EVIDENCE WORKSPACE", "section"), text(160, 988, "Durable state and research artifacts", "body")]
    for i, label in enumerate(["workspace/", "papers/", "datasets/", "structures/", "reports/", "approvals/", "calculations/"]):
        x = 565 + i * 235
        parts += [rect(x, 944, 205, 82, "#FFFFFF", 19, "#C8D7E7", 2), text(x + 102, 994, label, "artifact", None, "middle")]
    parts += ['<path d="M1200 1080V1120M340 1120H2060M340 1120V1150M910 1120V1150M1490 1120V1150M2060 1120V1150" fill="none" stroke="#92AAC3" stroke-width="7" marker-end="url(#arrow)"/>']
    parts += [source(120, "Literature", "papers · DOI · evidence", "#246BCE"), source(690, "Public datasets", "NCM · Zenodo · manifests", "#7C4DDB"), source(1260, "Materials databases", "MP · JARVIS · Matbench", "#138A61"), source(1830, "User HPC cluster", "SSH · Slurm · VASP/QE", "#D56A25", True)]
    parts += [text(120, 1318, "Agent orchestration stays flexible. Scientific execution stays reproducible.", "artifact", "#6D7D91"), text(1865, 1318, "new-energy-agent", "artifact", "#246BCE"), "</svg>"]
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text("\n".join(parts), encoding="utf-8")
    print(f"wrote {OUT} ({OUT.stat().st_size:,} bytes)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
