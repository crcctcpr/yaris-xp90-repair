"""Parse YarisRepair/engine/DTC_FULL_DATABASE.md into DtcEntry records.

The markdown KB has 127 DTCs with consistent structure:

    ### P0101
    **Description:** ...
    **Symptoms:**
    - item
    - item
    **Causes (ranked):**
    - item
    **Fixes:**
    1. step
    **Parts:** text
    **DIY Difficulty:** Easy/Medium/Hard/Expert

This module reads that file and merges entries into dtc_db.DTC_DATABASE at
import time, so the DB always reflects the KB.
"""
import os
import re

# The repair KB ships alongside this package: <repo>/repair-kb/.
# `diag/yaris/dtc_kb_parser.py` -> up 3 -> <repo>/repair-kb/...
# Override with YARIS_KB_PATH if you keep the KB elsewhere.
_REPO_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
DTC_KB_PATH = os.environ.get(
    "YARIS_KB_PATH",
    os.path.join(_REPO_ROOT, "repair-kb", "engine", "DTC_FULL_DATABASE.md"),
)

# System classification by code prefix range
SYSTEM_BY_PREFIX = [
    # (regex, system, severity)
    (re.compile(r"^P001[0-2]$"), "engine", "warn"),       # VVT-i solenoid circuits
    (re.compile(r"^P001[6-9]$"), "engine", "warn"),       # Timing correlation
    (re.compile(r"^P01[0-3]"),  "fuel", "warn"),           # MAF, MAP, IAT
    (re.compile(r"^P011[5-9]$"), "cooling", "warn"),       # ECT sensor
    (re.compile(r"^P01[2-3]"),  "cooling", "warn"),        # Thermostat / ECT
    (re.compile(r"^P0135$"),    "emissions", "warn"),      # O2 heater
    (re.compile(r"^P0141$"),    "emissions", "warn"),
    (re.compile(r"^P0171$"),    "fuel", "warn"),
    (re.compile(r"^P0172$"),    "fuel", "warn"),
    (re.compile(r"^P020"),      "fuel", "warn"),           # Injector
    (re.compile(r"^P02[12]"),   "fuel", "warn"),
    (re.compile(r"^P030[0-4]"), "ignition", "warn"),       # Misfire
    (re.compile(r"^P033[0-9]"), "ignition", "critical"),   # CKP
    (re.compile(r"^P034[0-9]"), "ignition", "critical"),   # CMP
    (re.compile(r"^P040[0-9]"), "emissions", "warn"),      # EGR
    (re.compile(r"^P0420$"),    "emissions", "warn"),      # Cat efficiency
    (re.compile(r"^P044"),      "emissions", "minor"),     # EVAP
    (re.compile(r"^P045"),      "emissions", "minor"),     # EVAP
    (re.compile(r"^P05[0-5]"),  "engine", "warn"),         # Idle / VSS
    (re.compile(r"^P06[0-9]"),  "engine", "warn"),
    (re.compile(r"^P07[0-2]"),  "drivetrain", "warn"),     # Trans
    (re.compile(r"^P0685$"),    "electrical", "warn"),
    (re.compile(r"^P13"),       "ignition", "warn"),
    (re.compile(r"^P1349$"),    "engine", "warn"),
    (re.compile(r"^P1135$"),    "emissions", "warn"),
    (re.compile(r"^P1155$"),    "emissions", "warn"),
    (re.compile(r"^P2[12][0-9]{2}$"), "fuel", "warn"),
    (re.compile(r"^C"),         "abs", "warn"),
    (re.compile(r"^B"),         "srs", "warn"),
    (re.compile(r"^U"),         "electrical", "critical"),
]

DIFFICULTY_MAP = {"easy": 1, "medium": 3, "moderate": 3, "hard": 4, "expert": 5}


def _classify(code: str) -> tuple[str, str]:
    for pattern, sys, sev in SYSTEM_BY_PREFIX:
        if pattern.match(code):
            return sys, sev
    # Default by prefix letter
    if code.startswith("P"):
        return "engine", "warn"
    if code.startswith("C"):
        return "abs", "warn"
    if code.startswith("B"):
        return "srs", "warn"
    if code.startswith("U"):
        return "electrical", "warn"
    return "engine", "warn"


def _parse_difficulty(text: str) -> int:
    if not text:
        return 3
    t = text.strip().lower()
    for key, val in DIFFICULTY_MAP.items():
        if key in t:
            return val
    return 3


def _parse_cost_from_parts(parts_str: str) -> tuple[tuple[int, int], tuple[int, int]]:
    """Best-effort extract of cost range from parts text like 'OEM $80-$120, Aftermarket $30-$60'."""
    import re as _re
    prices = _re.findall(r"\$(\d+)\s*[-–]\s*\$?(\d+)", parts_str or "")
    if not prices:
        prices = _re.findall(r"\$(\d+)", parts_str or "")
        prices = [(p, p) for p in prices]
    if not prices:
        return ((0, 0), (0, 0))
    all_nums = [int(a) for a, _ in prices] + [int(b) for _, b in prices]
    lo = min(all_nums)
    hi = max(all_nums)
    diy = (lo, min(hi, lo * 3 + 40))  # rough heuristic — aftermarket cheaper
    shop = (max(diy[1], lo + 100), hi * 2 + 100)
    return (diy, shop)


def parse_kb() -> list[dict]:
    """Return list of dicts with fields matching DtcEntry."""
    if not os.path.exists(DTC_KB_PATH):
        return []
    with open(DTC_KB_PATH) as f:
        content = f.read()

    entries = []
    # Split on "### CODE" headers
    chunks = re.split(r"^### ([A-Z]\d{4,})\s*$", content, flags=re.MULTILINE)
    # chunks: ["preamble", "P0010", body, "P0011", body, ...]
    for i in range(1, len(chunks), 2):
        code = chunks[i].strip()
        body = chunks[i + 1] if i + 1 < len(chunks) else ""

        def _extract(label, multi=False):
            # Look for "**Label:**" and read until next "**" header
            m = re.search(rf"\*\*{re.escape(label)}:?\*\*\s*(.+?)(?=\n\*\*|\n---|\Z)",
                          body, re.DOTALL)
            if not m:
                return [] if multi else ""
            text = m.group(1).strip()
            if not multi:
                return text
            # Parse list items (- or numbered)
            items = []
            for line in text.split("\n"):
                line = line.strip()
                if not line:
                    continue
                m2 = re.match(r"^[-*]\s+(.+)$", line) or re.match(r"^\d+\.\s+(.+)$", line)
                if m2:
                    items.append(m2.group(1).strip())
            return items

        desc = _extract("Description")
        symptoms = _extract("Symptoms", multi=True)
        causes = _extract("Causes", multi=True) or _extract("Causes (ranked)", multi=True)
        fixes = _extract("Fixes", multi=True)
        parts_line = _extract("Parts")
        diff_line = _extract("DIY Difficulty")

        system, severity = _classify(code)
        (diy_cost, shop_cost) = _parse_cost_from_parts(parts_line)

        # Extract title from description (first part before em-dash or period)
        title = desc.split("—")[0].split(" - ")[0].split(".")[0].strip()
        if len(title) > 80:
            title = title[:77] + "..."
        if not title:
            title = code

        entries.append({
            "code": code,
            "title": title,
            "severity": severity,
            "system": system,
            "symptoms": symptoms,
            "causes": causes,
            "diy_steps": fixes,
            "parts": [parts_line] if parts_line else [],
            "cost_diy_usd": diy_cost,
            "cost_shop_usd": shop_cost,
            "difficulty": _parse_difficulty(diff_line),
            "notes": "",
            "kb_links": ["engine/DTC_FULL_DATABASE.md"],
        })
    return entries


def merge_into(db: dict):
    """Merge parsed entries into an existing DTC_DATABASE dict in-place.

    Entries with the same code: existing curated entry wins (don't overwrite
    the handcrafted richer ones). Missing codes: add.
    """
    from .dtc_db import DtcEntry
    for entry in parse_kb():
        code = entry["code"].upper()
        if code in db:
            # Already curated — merge in any missing fields
            existing = db[code]
            if not existing.symptoms and entry["symptoms"]:
                existing.symptoms = entry["symptoms"]
            if not existing.causes and entry["causes"]:
                existing.causes = entry["causes"]
            if not existing.diy_steps and entry["diy_steps"]:
                existing.diy_steps = entry["diy_steps"]
        else:
            # New — add
            db[code] = DtcEntry(
                code=code, title=entry["title"],
                severity=entry["severity"], system=entry["system"],
                symptoms=entry["symptoms"], causes=entry["causes"],
                diy_steps=entry["diy_steps"], parts=entry["parts"],
                cost_diy_usd=entry["cost_diy_usd"],
                cost_shop_usd=entry["cost_shop_usd"],
                difficulty=entry["difficulty"],
                kb_links=entry["kb_links"], notes=entry["notes"],
            )
