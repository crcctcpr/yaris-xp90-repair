"""In-use Performance Tracking (IPT) — Mode 09 PID 0x08.

The ECU keeps per-monitor counters:
  - "numerator": how many times the monitor's enabling conditions were met
  - "denominator": how many times the monitor actually ran to completion

Ratio (numerator / denominator) is what CARB/EPA use to verify that OBD-II
monitors are actually running, not just being reported as "complete". A
healthy car shows ratios near 1.0 (monitor always runs when conditions met).

Per SAE J1979, IPT for spark-ignition vehicles returns 20 16-bit words:

  word  meaning
  0     OBDCOND     (general engine conditions met)
  1     IGNCNTR     (ignition cycle counter)
  2     CATCOMP1    (catalyst monitor completions B1)
  3     CATCOND1    (catalyst conditions met B1)
  4     CATCOMP2    (catalyst B2)
  5     CATCOND2
  6     O2SCOMP1    (O2 sensor monitor completions B1)
  7     O2SCOND1    (O2 sensor conditions B1)
  8     O2SCOMP2
  9     O2SCOND2
  10    EGRCOMP     (EGR monitor completions)
  11    EGRCOND
  12    AIRCOMP     (secondary air)
  13    AIRCOND
  14    EVAPCOMP    (EVAP leak)
  15    EVAPCOND
  16    SO2SCOMP1   (secondary O2 B1)
  17    SO2SCOND1
  18    SO2SCOMP2
  19    SO2SCOND2

We already get this from the full-pull script — this decoder turns raw bytes
into human-readable ratios.
"""
from dataclasses import dataclass

from .elm import Elm
from .obd import read_pid


IPT_FIELDS = [
    ("obdcond", "General OBD conditions", None, None),
    ("igncntr", "Ignition cycles", None, None),
    ("cat_comp_b1", "Catalyst B1 completions", "cat_cond_b1", "Catalyst B1"),
    ("cat_cond_b1", "Catalyst B1 conditions met", None, None),
    ("cat_comp_b2", "Catalyst B2 completions", "cat_cond_b2", "Catalyst B2"),
    ("cat_cond_b2", "Catalyst B2 conditions met", None, None),
    ("o2s_comp_b1", "O2 Sensor B1 completions", "o2s_cond_b1", "O2 Sensor B1"),
    ("o2s_cond_b1", "O2 Sensor B1 conditions met", None, None),
    ("o2s_comp_b2", "O2 Sensor B2 completions", "o2s_cond_b2", "O2 Sensor B2"),
    ("o2s_cond_b2", "O2 Sensor B2 conditions met", None, None),
    ("egr_comp", "EGR completions", "egr_cond", "EGR"),
    ("egr_cond", "EGR conditions met", None, None),
    ("air_comp", "Secondary air completions", "air_cond", "Secondary Air"),
    ("air_cond", "Secondary air conditions met", None, None),
    ("evap_comp", "EVAP completions", "evap_cond", "EVAP"),
    ("evap_cond", "EVAP conditions met", None, None),
    ("so2s_comp_b1", "Secondary O2 B1 completions", "so2s_cond_b1", "Sec O2 B1"),
    ("so2s_cond_b1", "Secondary O2 B1 conditions met", None, None),
    ("so2s_comp_b2", "Secondary O2 B2 completions", "so2s_cond_b2", "Sec O2 B2"),
    ("so2s_cond_b2", "Secondary O2 B2 conditions met", None, None),
]


@dataclass
class IPTResult:
    raw_hex: str
    fields: dict
    monitor_ratios: list[dict]
    ign_cycles: int


def decode_ipt(payload: bytes) -> IPTResult:
    """Decode the raw IPT byte sequence into a structured result."""
    # First byte may be a count of items; skip it if present.
    data = payload
    if len(data) % 2 == 1:
        # Odd length — probably leading count byte
        data = data[1:]

    words = []
    for i in range(0, len(data) - 1, 2):
        words.append((data[i] << 8) | data[i + 1])

    fields = {}
    for i, (key, label, _, _) in enumerate(IPT_FIELDS):
        if i < len(words):
            fields[key] = words[i]

    # Compute ratios for monitors that have completion+condition pairs
    ratios = []
    for key, label, cond_key, mon_name in IPT_FIELDS:
        if cond_key is None:
            continue
        comp = fields.get(key, 0)
        cond = fields.get(cond_key, 0)
        if cond == 0:
            ratio = 0.0
            status = "never ran"
        else:
            ratio = comp / cond
            if ratio >= 0.95:
                status = "healthy"
            elif ratio >= 0.50:
                status = "ok"
            elif ratio >= 0.20:
                status = "low"
            else:
                status = "very low"
        ratios.append({
            "monitor": mon_name,
            "completions": comp,
            "conditions_met": cond,
            "ratio": round(ratio, 3),
            "ratio_pct": round(ratio * 100, 1),
            "status": status,
        })

    return IPTResult(
        raw_hex=payload.hex(),
        fields=fields,
        monitor_ratios=ratios,
        ign_cycles=fields.get("igncntr", 0),
    )


def read_ipt(elm: Elm) -> IPTResult | None:
    """Query 09 08 and decode the IPT response."""
    payload = read_pid(elm, "0908", 3.0)
    if not payload:
        return None
    return decode_ipt(payload)


def decode_hex_string(hex_str: str) -> IPTResult:
    """Decode IPT from a hex string (useful for already-captured data)."""
    clean = hex_str.replace(" ", "").replace(":", "")
    payload = bytes.fromhex(clean)
    return decode_ipt(payload)
