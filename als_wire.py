#!/usr/bin/env python3
"""als-wire — wire plugin parameters to rack macros and MIDI mappings
directly inside Ableton Live ``.als`` project files. Batch, scriptable,
no GUI clicking.

An ``.als`` is gzip-compressed XML. Everything this tool writes uses
structures learned from files authored by Live itself (Live 12.4, macOS);
see ``docs/als-format-notes.md`` for the reverse-engineering notes.

Commands:
    inspect  PROJECT.als [--track NAME]     show tracks / racks / devices /
                                            exposed params / MIDI mappings
    wire     PROJECT.als SPEC.json          apply a wiring spec
             [--out OUT.als | --in-place]

Safety: the input file is ALWAYS backed up first (``<file>.bak-<timestamp>``)
and by default the result is written to a NEW file (``<stem> WIRED.als``).

Spec example (see examples/): expose two SWAM parameters on every matching
device, map them to macros 1-2 of the enclosing rack, chain nested-rack
macros up to the top rack, name the top macros, and MIDI-map them:

    {
      "track": "Lead",
      "macros": {"1": "Growl", "2": "Flutter"},
      "midi_maps": {"1": [1, 12], "2": [1, 13]},
      "chain_nested": true,
      "devices": [
        {"plugin": "SWAM Trumpet",
         "params": [
           {"name": "Growl",          "id": "juce:growl",         "macro": 1},
           {"name": "Flutter Tongue", "id": "juce:flutterTongue", "macro": 2}
         ]}
      ]
    }

``"id"`` accepts a raw signed-int32 VST3 ParamID or ``"juce:<internalName>"``
— JUCE-based plugins (SWAM, many others) derive their VST3 ParamID from the
Java-style ``String.hashCode()`` of the parameter's internal ID string.
``"value"`` (optional, default 0.0) is the parameter's initial value in
Live's ParameterValue/Manual field — for plugin parameters this is the
normalized 0..1 host value, NOT the plugin's display value; leave params at
their neutral 0 unless you know the right normalized value.
"""
import argparse
import gzip
import json
import os
import shutil
import sys
import time
import xml.etree.ElementTree as ET

TRACK_TAGS = ("MidiTrack", "AudioTrack", "GroupTrack", "ReturnTrack")
DEVICE_TAGS = ("PluginDevice", "AuPluginDevice")


def jhash(s: str) -> int:
    """Java String.hashCode() as signed int32 (JUCE -> VST3 ParamID)."""
    h = 0
    for c in s:
        h = (31 * h + ord(c)) & 0xFFFFFFFF
    return h - 2**32 if h >= 2**31 else h


def load(path: str) -> ET.Element:
    with gzip.open(path, "rb") as f:
        return ET.fromstring(f.read().decode("utf-8"))


def save(root: ET.Element, path: str) -> None:
    data = b'<?xml version="1.0" encoding="UTF-8"?>\n' + \
        ET.tostring(root, encoding="unicode").encode("utf-8") + b"\n"
    with gzip.open(path, "wb") as f:
        f.write(data)


def keymidi(channel0: int, controller: int) -> ET.Element:
    """A Live mapping block. channel0: 0-15 = real MIDI channel (0-based),
    16 = the internal 'enclosing rack macro' pseudo-bus."""
    km = ET.Element("KeyMidi")
    for tag, val in (("PersistentKeyString", ""), ("IsNote", "false"),
                     ("Channel", str(channel0)), ("NoteOrController", str(controller)),
                     ("LowerRangeNote", "-1"), ("UpperRangeNote", "-1"),
                     ("ControllerMapMode", "0")):
        ET.SubElement(km, tag).set("Value", val)
    return km


def insert_keymidi(container: ET.Element, channel0: int, controller: int) -> None:
    if container.find("KeyMidi") is not None:
        raise SystemExit("target already has a KeyMidi mapping — refusing to overwrite")
    lom = container.find("LomId")
    idx = list(container).index(lom) + 1 if lom is not None else 0
    container.insert(idx, keymidi(channel0, controller))


def setval(parent: ET.Element, tag: str, value) -> None:
    e = parent.find(tag)
    if e is None:
        raise SystemExit(f"element {tag} not found")
    e.set("Value", str(value))


def plugin_name(dev: ET.Element) -> str | None:
    for path in (".//Vst3PluginInfo/Name", ".//AuPluginInfo/Name", ".//VstPluginInfo/PlugName"):
        e = dev.find(path)
        if e is not None and e.get("Value"):
            return e.get("Value")
    return None


def effective_name(el: ET.Element) -> str:
    e = el.find("Name/EffectiveName")
    return e.get("Value") if e is not None else "?"


def build_parent_map(root: ET.Element) -> dict:
    return {c: p for p in root.iter() for c in p}


def enclosing_racks(el: ET.Element, parents: dict) -> list:
    out, n = [], el
    while n in parents:
        n = parents[n]
        if n.tag == "InstrumentGroupDevice":
            out.append(n)
    return out


def find_track(root: ET.Element, name: str) -> ET.Element:
    for tag in TRACK_TAGS:
        for tr in root.iter(tag):
            if effective_name(tr) == name:
                return tr
    raise SystemExit(f"track {name!r} not found")


# ---------------------------------------------------------------- inspect --
def cmd_inspect(args) -> None:
    root = load(args.project)
    parents = build_parent_map(root)
    for tag in TRACK_TAGS:
        for tr in root.iter(tag):
            tname = effective_name(tr)
            if args.track and tname != args.track:
                continue
            devs = [d for t in DEVICE_TAGS for d in tr.iter(t)]
            racks = list(tr.iter("InstrumentGroupDevice"))
            if not devs and not racks:
                continue
            print(f"track [{tag}] {tname!r}: {len(racks)} rack(s), {len(devs)} plugin device(s)")
            for rk in racks:
                depth = len(enclosing_racks(rk, parents))
                named = [(i, rk.find(f"MacroDisplayNames.{i}").get("Value"))
                         for i in range(16)
                         if rk.find(f"MacroDisplayNames.{i}") is not None
                         and rk.find(f"MacroDisplayNames.{i}").get("Value") != f"Macro {i+1}"]
                mapped = [(i, k.find("Channel").get("Value"), k.find("NoteOrController").get("Value"))
                          for i in range(16)
                          for k in [rk.find(f"MacroControls.{i}/KeyMidi")] if k is not None]
                print("  " * (depth + 1) + f"rack: macros named={named or '—'} mapped={mapped or '—'}")
            for d in devs:
                pn = plugin_name(d) or d.tag
                exposed = []
                for p in d.iter("PluginFloatParameter"):
                    nm = p.find("ParameterName").get("Value")
                    pid = p.find("ParameterId").get("Value")
                    if pid != "-1" and nm:
                        km = p.find("ParameterValue/KeyMidi")
                        tgt = (f" ->ch{int(km.find('Channel').get('Value'))+1}/"
                               f"CC{km.find('NoteOrController').get('Value')}"
                               if km is not None else "")
                        if km is not None and km.find("Channel").get("Value") == "16":
                            tgt = f" ->macro{int(km.find('NoteOrController').get('Value'))+1}"
                        exposed.append(nm + tgt)
                depth = len(enclosing_racks(d, parents))
                print("  " * (depth + 1) + f"device {pn} [{d.tag}]"
                      + (f" exposed: {', '.join(exposed)}" if exposed else ""))


# ------------------------------------------------------------------- wire --
def resolve_id(v) -> int:
    if isinstance(v, int):
        return v
    if isinstance(v, str) and v.startswith("juce:"):
        return jhash(v[5:])
    raise SystemExit(f"invalid param id {v!r} (int or 'juce:<name>')")


def cmd_wire(args) -> None:
    spec = json.load(open(args.spec))
    root = load(args.project)
    parents = build_parent_map(root)
    track = find_track(root, spec["track"])
    top = next(iter(track.iter("InstrumentGroupDevice")), None)
    if top is None:
        raise SystemExit(f"no Instrument Rack on track {spec['track']!r}")

    report, wired_inner, used_macros = [], set(), set()
    for dspec in spec.get("devices", []):
        matches = [d for t in DEVICE_TAGS for d in top.iter(t)
                   if plugin_name(d) == dspec["plugin"]]
        if not matches:
            report.append(f"⚠ no device matches plugin {dspec['plugin']!r}")
            continue
        for dev in matches:
            racks = enclosing_racks(dev, parents)
            inner = racks[0] if racks and racks[0] is not top else top
            slots = [s for s in dev.iter("PluginFloatParameter")
                     if s.find("ParameterId").get("Value") == "-1"
                     and not s.find("ParameterName").get("Value")]
            if len(slots) < len(dspec["params"]):
                raise SystemExit(f"{dspec['plugin']}: not enough empty parameter slots")
            for vi, (pspec, slot) in enumerate(zip(dspec["params"], slots)):
                setval(slot, "ParameterName", pspec["name"])
                setval(slot, "ParameterId", resolve_id(pspec["id"]))
                setval(slot, "VisualIndex", vi)
                pv = slot.find("ParameterValue")
                setval(pv, "Manual", pspec.get("value", 0.0))
                if "macro" in pspec:
                    insert_keymidi(pv, 16, pspec["macro"] - 1)
                    used_macros.add(pspec["macro"])
                    if inner is not top:
                        wired_inner.add(id(inner))
            report.append(f"{dspec['plugin']} [{dev.tag}]: "
                          f"{len(dspec['params'])} param(s) exposed"
                          + (" (nested rack)" if inner is not top else ""))

    inner_by_id = {id(r): r for r in top.iter("InstrumentGroupDevice")}
    if spec.get("chain_nested") and wired_inner:
        for rid in wired_inner:
            rack = inner_by_id[rid]
            for m in sorted(used_macros):
                insert_keymidi(rack.find(f"MacroControls.{m-1}"), 16, m - 1)
                name = spec.get("macros", {}).get(str(m))
                if name:
                    setval(rack, f"MacroDisplayNames.{m-1}", name)
        report.append(f"chained macros {sorted(used_macros)} of {len(wired_inner)} "
                      f"nested rack(s) to the top rack")

    for m, name in spec.get("macros", {}).items():
        setval(top, f"MacroDisplayNames.{int(m)-1}", name)
    for m, (channel, cc) in spec.get("midi_maps", {}).items():
        insert_keymidi(top.find(f"MacroControls.{int(m)-1}"), channel - 1, cc)
        report.append(f"top macro {m} <- MIDI ch{channel}/CC{cc}")

    bak = args.project + ".bak-" + time.strftime("%Y%m%d-%H%M%S")
    shutil.copy2(args.project, bak)
    out = args.project if args.in_place else \
        (args.out or args.project.replace(".als", " WIRED.als"))
    save(root, out)

    chk = load(out)
    n16 = sum(1 for k in chk.iter("KeyMidi") if k.find("Channel").get("Value") == "16")
    print("\n".join(report))
    print(f"\nwrote  : {out}\nbackup : {bak}\ncheck  : {n16} internal (ch16) mappings in output")


if __name__ == "__main__":
    ap = argparse.ArgumentParser(prog="als-wire", description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = ap.add_subparsers(dest="cmd", required=True)
    p1 = sub.add_parser("inspect", help="show tracks / racks / devices / mappings")
    p1.add_argument("project")
    p1.add_argument("--track")
    p1.set_defaults(func=cmd_inspect)
    p2 = sub.add_parser("wire", help="apply a wiring spec (backup + new file)")
    p2.add_argument("project")
    p2.add_argument("spec")
    p2.add_argument("--out")
    p2.add_argument("--in-place", action="store_true")
    p2.set_defaults(func=cmd_wire)
    a = ap.parse_args()
    a.func(a)
