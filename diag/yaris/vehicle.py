"""Vehicle constants + profile loader.

Profiles live in `yaris/vehicles/<VIN>.toml`. The default profile is the
2011 Yaris we've been working on. Call `load_profile("<VIN>")` (or pass
`--vehicle <VIN>` via the CLI) to switch.

All public names are module-level constants so existing code keeps working:
    from yaris.vehicle import DEFAULT_PORT, VIN, expected_maf
When a profile is loaded, the module-level constants are updated in place.
"""
import os
import sys
from pathlib import Path

# Python 3.11+ has tomllib stdlib. Fall back gracefully if not available.
try:
    import tomllib
    _HAS_TOML = True
except ImportError:
    _HAS_TOML = False


# ── Paths ───────────────────────────────────────────────────────────────
_HERE = Path(__file__).resolve().parent
VEHICLES_DIR = _HERE / "vehicles"
# Where scan logs/reports are written. Override with YARIS_REPORT_DIR.
# Defaults to a `reports/` dir next to the `diag/` package.
REPORT_DIR = os.environ.get("YARIS_REPORT_DIR", str(_HERE.parent / "reports"))
TOOLS_DIR = str(_HERE.parent)
# Placeholder VIN for the bundled example profile. Replace with your own VIN
# (set YARIS_VIN or pass --vehicle) and add vehicles/<YOUR_VIN>.toml.
DEFAULT_VIN = "JTDEXAMPLE0000000"

# ── Default values (will be overwritten when a profile loads) ──────────
# These are kept synchronized with vehicles/JTDEXAMPLE0000000.toml.
VIN = "JTDEXAMPLE0000000"
MODEL_YEAR = 2011
PLATFORM = "XP90"
ENGINE = "1NR-FE"
ENGINE_DISPLACEMENT_L = 1.329
TRANS_CANDIDATES = ["C50 5MT", "U340E 4AT"]
PROTOCOL_NUMBER = 6

ELM_MAC = "AA:BB:CC:DD:EE:FF"
ELM_PIN = "1234"
ELM_SPP_CHANNEL = 2
DEFAULT_PORT = "/dev/rfcomm0"
DEFAULT_BAUD = 38400

ECM_REQ = "7E0"
ECM_RESP = "7E8"
FUNCTIONAL_BROADCAST = "7DF"

EXPECTED_IDLE_RPM = (650, 850)
EXPECTED_COOLANT_WARM_C = (85, 98)
EXPECTED_IAT_C = (10, 60)
EXPECTED_BATT_V_ENGINE_OFF = (12.0, 12.7)
EXPECTED_BATT_V_ENGINE_RUNNING = (13.4, 14.5)
EXPECTED_STFT_PCT = (-7.0, 7.0)
EXPECTED_LTFT_PCT = (-7.0, 7.0)
EXPECTED_MAF_IDLE_GS = (2.0, 4.5)
EXPECTED_LAMBDA = (0.97, 1.03)
EXPECTED_TIMING_ADV_IDLE = (4.0, 14.0)
EXPECTED_CAT_TEMP_C = (400, 750)

AIR_DENSITY_G_L = 1.20

_active_profile = None


# ── Profile loader ──────────────────────────────────────────────────────
def list_profiles() -> list[str]:
    """Return list of VINs we have profiles for."""
    if not VEHICLES_DIR.exists():
        return []
    return sorted(
        p.stem for p in VEHICLES_DIR.glob("*.toml")
        if p.stem != "_template"
    )


def load_profile(vin_or_path: str | Path) -> dict:
    """Load a vehicle profile and update module globals.

    Accepts either a VIN (looked up in `vehicles/<VIN>.toml`) or an explicit
    file path. Returns the parsed profile dict. Raises FileNotFoundError if
    not found, RuntimeError if tomllib isn't available.
    """
    if not _HAS_TOML:
        raise RuntimeError("tomllib not available (needs Python 3.11+)")

    path = Path(vin_or_path)
    if not path.exists():
        path = VEHICLES_DIR / f"{vin_or_path}.toml"
    if not path.exists():
        raise FileNotFoundError(f"No profile found for {vin_or_path}")

    with open(path, "rb") as f:
        cfg = tomllib.load(f)

    # Apply to module globals
    g = sys.modules[__name__]
    ident = cfg.get("identity", {})
    g.VIN = ident.get("vin", g.VIN)
    g.MODEL_YEAR = ident.get("model_year", g.MODEL_YEAR)
    g.PLATFORM = ident.get("platform", g.PLATFORM)
    g.ENGINE = ident.get("engine", g.ENGINE)
    g.ENGINE_DISPLACEMENT_L = ident.get("engine_displacement_l", g.ENGINE_DISPLACEMENT_L)
    g.TRANS_CANDIDATES = ident.get("trans_candidates", g.TRANS_CANDIDATES)

    adapter = cfg.get("adapter", {})
    g.ELM_MAC = adapter.get("mac", g.ELM_MAC)
    g.ELM_PIN = adapter.get("pin", g.ELM_PIN)
    g.ELM_SPP_CHANNEL = adapter.get("spp_channel", g.ELM_SPP_CHANNEL)
    g.DEFAULT_PORT = adapter.get("default_port", g.DEFAULT_PORT)
    g.DEFAULT_BAUD = adapter.get("default_baud", g.DEFAULT_BAUD)

    proto = cfg.get("protocol", {})
    g.PROTOCOL_NUMBER = proto.get("elm_protocol_number", g.PROTOCOL_NUMBER)
    g.ECM_REQ = proto.get("ecm_request_id", g.ECM_REQ)
    g.ECM_RESP = proto.get("ecm_response_id", g.ECM_RESP)
    g.FUNCTIONAL_BROADCAST = proto.get("functional_broadcast", g.FUNCTIONAL_BROADCAST)

    exp = cfg.get("expected", {})
    # All expected ranges: accept list-of-2 from TOML, normalise to tuple
    def _t(key, cur):
        v = exp.get(key)
        return tuple(v) if v and len(v) == 2 else cur
    g.EXPECTED_IDLE_RPM              = _t("idle_rpm", g.EXPECTED_IDLE_RPM)
    g.EXPECTED_COOLANT_WARM_C        = _t("coolant_warm_c", g.EXPECTED_COOLANT_WARM_C)
    g.EXPECTED_IAT_C                 = _t("iat_c", g.EXPECTED_IAT_C)
    g.EXPECTED_BATT_V_ENGINE_OFF     = _t("batt_v_engine_off", g.EXPECTED_BATT_V_ENGINE_OFF)
    g.EXPECTED_BATT_V_ENGINE_RUNNING = _t("batt_v_engine_running", g.EXPECTED_BATT_V_ENGINE_RUNNING)
    g.EXPECTED_STFT_PCT              = _t("stft_pct", g.EXPECTED_STFT_PCT)
    g.EXPECTED_LTFT_PCT              = _t("ltft_pct", g.EXPECTED_LTFT_PCT)
    g.EXPECTED_MAF_IDLE_GS           = _t("maf_idle_gs", g.EXPECTED_MAF_IDLE_GS)
    g.EXPECTED_LAMBDA                = _t("lambda_value", g.EXPECTED_LAMBDA)
    g.EXPECTED_TIMING_ADV_IDLE       = _t("timing_adv_idle", g.EXPECTED_TIMING_ADV_IDLE)
    g.EXPECTED_CAT_TEMP_C            = _t("cat_temp_c", g.EXPECTED_CAT_TEMP_C)

    phys = cfg.get("physics", {})
    g.AIR_DENSITY_G_L = phys.get("air_density_g_l", g.AIR_DENSITY_G_L)

    g._active_profile = cfg
    return cfg


def active_profile() -> dict | None:
    return _active_profile


def auto_load_default():
    """Called at import time — loads the default VIN profile if available.
    Silently keeps built-in defaults if profile missing or toml unavailable."""
    try:
        env_vin = os.environ.get("YARIS_VIN")
        target = env_vin or DEFAULT_VIN
        load_profile(target)
    except Exception:
        pass


# ── Physical model (unchanged) ──────────────────────────────────────────
def expected_maf(rpm, load_pct=None, throttle_pct=None, mode="throttle"):
    """Expected MAF g/s for this vehicle.

    Volumetric eq: MAF = (disp/2) × (rpm/60) × VE × air_density.
    VE source:
      - "throttle": independent of MAF (best for MAF diagnosis)
      - "load": ECU-computed load (circular if MAF is faulty)
      - "rpm_only": RPM-based curve only
    """
    if rpm < 300:
        return 0.0

    if mode == "load":
        if load_pct is None:
            load_pct = 30.0
        ve = 0.30 + 0.65 * max(0.0, min(1.0, load_pct / 100.0))
    elif mode == "throttle":
        if throttle_pct is None:
            ve = _ve_from_rpm(rpm)
        else:
            t = max(0.0, min(1.0, (throttle_pct - 14.0) / 71.0))
            ve = 0.30 + 0.62 * (t ** 0.5)
    else:
        ve = _ve_from_rpm(rpm)

    return (ENGINE_DISPLACEMENT_L / 2.0) * (rpm / 60.0) * ve * AIR_DENSITY_G_L


def _ve_from_rpm(rpm):
    """Part-throttle VE curve fallback."""
    pts = [(600, 0.28), (1000, 0.40), (1500, 0.55), (2500, 0.70),
           (3500, 0.78), (5000, 0.88), (6500, 0.88)]
    for (r1, v1), (r2, v2) in zip(pts, pts[1:]):
        if rpm <= r2:
            frac = (rpm - r1) / (r2 - r1)
            return v1 + frac * (v2 - v1)
    return pts[-1][1]


# Auto-load on module import
auto_load_default()
