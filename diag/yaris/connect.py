"""Robust Bluetooth + rfcomm connection helper for the ELM327."""
import os
import subprocess
import time
from .vehicle import ELM_MAC, ELM_SPP_CHANNEL, DEFAULT_PORT


def _run(cmd, check=False, timeout=15):
    try:
        r = subprocess.run(cmd, capture_output=True, text=True, timeout=timeout)
        return r.returncode, r.stdout, r.stderr
    except subprocess.TimeoutExpired:
        return 124, "", "timeout"


def rfcomm_state(port=DEFAULT_PORT) -> dict:
    """Return current state: exists/permissions/bound/connected."""
    out = {"device": port, "exists": os.path.exists(port)}
    rc, so, _ = _run(["sudo", "-n", "rfcomm", "-a"])
    out["rfcomm_list"] = so.strip()
    out["bound"] = port.replace("/dev/", "") in so
    out["state"] = None
    for line in so.splitlines():
        if port.replace("/dev/", "") in line:
            parts = line.split()
            # Format: "rfcomm0: MAC channel N STATE"
            if len(parts) >= 5:
                out["state"] = parts[4]
    return out


def ensure_bound(port=DEFAULT_PORT, mac=ELM_MAC, channel=ELM_SPP_CHANNEL, force_rebind=False) -> bool:
    """Ensure /dev/rfcomm0 is bound. Releases + re-binds if currently in a bad state."""
    st = rfcomm_state(port)
    if st["bound"] and not force_rebind and st["state"] in ("clean", "closed"):
        # Normalize permissions
        _run(["sudo", "-n", "chmod", "666", port])
        return True
    # Release and rebind
    _run(["sudo", "-n", "rfcomm", "release", port.replace("/dev/", "")])
    time.sleep(0.5)
    rc, so, se = _run(["sudo", "-n", "rfcomm", "bind", port.replace("/dev/", ""), mac, str(channel)])
    if rc != 0:
        print(f"[!] rfcomm bind failed: {se.strip()}")
        return False
    _run(["sudo", "-n", "chmod", "666", port])
    return os.path.exists(port)


def is_paired(mac=ELM_MAC) -> bool:
    rc, so, _ = _run(["bluetoothctl", "info", mac])
    return "Paired: yes" in so


def pair_via_dbus(mac=ELM_MAC) -> bool:
    """Kick off a pairing via direct D-Bus call. Assumes bt_pin_agent is running.

    This is the workaround for bluetoothctl's inline agent hijacking the PIN prompt.
    """
    mac_us = mac.replace(":", "_")
    path = f"/org/bluez/hci0/dev_{mac_us}"
    rc, so, se = _run([
        "sudo", "-n", "dbus-send", "--system", "--print-reply",
        f"--dest=org.bluez", path, "org.bluez.Device1.Pair",
    ], timeout=30)
    return rc == 0 and "method return" in so


def ensure_connected(port=DEFAULT_PORT) -> dict:
    """Best-effort bring the adapter online. Returns status dict for reporting."""
    status = {"port": port, "paired": is_paired(), "bound": False, "live": False, "notes": []}
    if not status["paired"]:
        status["notes"].append("Device not paired. Run the pair-via-dbus workflow before retrying.")
        return status
    status["bound"] = ensure_bound(port)
    if not status["bound"]:
        status["notes"].append("rfcomm bind failed — check bluez and adapter presence.")
        return status
    # Quick liveness check with ATZ
    try:
        from .elm import Elm
        with Elm(port) as e:
            e.wake()
            info = e.adapter_info()
            status["adapter"] = info
            status["live"] = "ELM" in info.get("id", "")
    except Exception as ex:
        status["notes"].append(f"Liveness probe failed: {ex}")
    return status
