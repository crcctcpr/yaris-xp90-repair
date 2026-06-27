"""
Yaris OBD2 toolkit — now multi-vehicle (Yaris + Mini + extensible).

Supported vehicles:
- 2011 Toyota Yaris XP90 / 1NR-FE 1.3L (primary)
- 2013 Mini Cooper Countryman R60 / N16 1.6L (added 2026-04-21)

Adapter: ELM327 clone over Bluetooth SPP → /dev/rfcomm0
Protocol: ISO 15765-4 CAN 11-bit 500 kbps for both

All diagnostic services used are READ-ONLY except the explicit clear tool:
- Safe reads:  01/02/03/06/07/09/0A (SAE), 19 (UDS DTCInfo), 21 (Toyota), 22 (UDS)
- Clear only:  04, gated behind audited code-clear tool.
- Never used:  08 (actuator), 10 (session), 27 (security), 2E/2F (write),
               31 (routine), 34/36/37 (flash), 3B (write DID).
"""
__version__ = "2.0"

# Load Mini bundle at import — registers issues/procedures/parts/DTCs/walkthroughs
try:
    from . import mini_knowledge  # noqa: F401 (side-effects install data)
    from . import mini_walkthroughs  # noqa: F401
except Exception:
    pass
