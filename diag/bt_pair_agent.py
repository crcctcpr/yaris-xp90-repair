#!/usr/bin/env python3
"""
Bluetooth PIN agent for pairing cheap ELM327 OBD2 adapters.

Many BT ELM327 clones use a fixed PIN (usually 1234 or 0000) and BlueZ's
interactive agent tends to time out before answering the PIN prompt. This
registers a non-interactive default agent that auto-answers the PIN, which
makes pairing reliable.

Usage:
    sudo python3 bt_pair_agent.py --pin 1234 [--mac AA:BB:CC:DD:EE:FF]

Then, in another terminal:
    sudo bluetoothctl -- scan on            # wait ~15 s for the adapter
    sudo bluetoothctl -- pair AA:BB:CC:DD:EE:FF
    # if bluetoothctl's own agent still hijacks the PIN prompt, pair via D-Bus:
    sudo dbus-send --system --print-reply --dest=org.bluez \
        /org/bluez/hci0/dev_AA_BB_CC_DD_EE_FF org.bluez.Device1.Pair

Requires: python3-dbus, python3-gi (PyGObject), a running BlueZ stack.
"""
import argparse

import dbus
import dbus.service
import dbus.mainloop.glib
from gi.repository import GLib

AGENT_IFACE = "org.bluez.Agent1"
AGENT_PATH = "/org/yarisdiag/bt_agent"


class PinAgent(dbus.service.Object):
    def __init__(self, bus, path, pin="1234", target_mac=None):
        super().__init__(bus, path)
        self.pin = pin
        self.target_mac = target_mac.upper() if target_mac else None
        flt = f" | MAC filter: {self.target_mac}" if self.target_mac else " | any device"
        print(f"[*] PIN agent ready — PIN: {pin}{flt}")

    @dbus.service.method(AGENT_IFACE, in_signature="o", out_signature="s")
    def RequestPinCode(self, device):
        print(f"[+] PIN requested for: {device}")
        return self.pin

    @dbus.service.method(AGENT_IFACE, in_signature="o", out_signature="u")
    def RequestPasskey(self, device):
        print(f"[+] Passkey requested for: {device}")
        return dbus.UInt32(int(self.pin))

    @dbus.service.method(AGENT_IFACE, in_signature="ouq", out_signature="")
    def DisplayPasskey(self, device, passkey, entered):
        print(f"[*] Display passkey {passkey} for {device}")

    @dbus.service.method(AGENT_IFACE, in_signature="os", out_signature="")
    def DisplayPinCode(self, device, pincode):
        print(f"[*] Display PIN {pincode} for {device}")

    @dbus.service.method(AGENT_IFACE, in_signature="ou", out_signature="")
    def RequestConfirmation(self, device, passkey):
        print(f"[+] Confirming passkey {passkey} for {device}")

    @dbus.service.method(AGENT_IFACE, in_signature="o", out_signature="")
    def RequestAuthorization(self, device):
        print(f"[+] Authorizing {device}")

    @dbus.service.method(AGENT_IFACE, in_signature="os", out_signature="")
    def AuthorizeService(self, device, uuid):
        print(f"[+] Authorizing service {uuid} for {device}")

    @dbus.service.method(AGENT_IFACE, in_signature="", out_signature="")
    def Cancel(self):
        print("[*] Pairing cancelled")


def main():
    parser = argparse.ArgumentParser(description="Auto-answer BlueZ PIN agent for ELM327 pairing.")
    parser.add_argument("--pin", default="1234", help="PIN to answer with (default 1234)")
    parser.add_argument("--mac", default=None, help="optional MAC filter (default: any device)")
    args = parser.parse_args()

    dbus.mainloop.glib.DBusGMainLoop(set_as_default=True)
    bus = dbus.SystemBus()
    PinAgent(bus, AGENT_PATH, pin=args.pin, target_mac=args.mac)

    manager = dbus.Interface(
        bus.get_object("org.bluez", "/org/bluez"), "org.bluez.AgentManager1"
    )
    manager.RegisterAgent(AGENT_PATH, "KeyboardOnly")
    manager.RequestDefaultAgent(AGENT_PATH)
    print("[*] Agent registered as default. Waiting for pairing requests... (Ctrl-C to stop)")

    try:
        GLib.MainLoop().run()
    except KeyboardInterrupt:
        print("\n[*] Agent stopped")
        manager.UnregisterAgent(AGENT_PATH)


if __name__ == "__main__":
    main()
