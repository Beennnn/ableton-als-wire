# als-wire

Wire plugin parameters to rack macros and MIDI mappings **directly inside
Ableton Live `.als` project files** — batch, scriptable, reproducible. No GUI
clicking, no per-parameter Configure + right-click + map session.

Built for a real use case: exposing `growl`/`flutter`-type parameters on nine
SWAM instruments spread across nested racks, mapping them all to two top-level
macros, and MIDI-mapping those macros — 60+ wirings in one command instead of
an afternoon of mouse work.

Python 3 standard library only. **Unofficial**: the `.als` format is
undocumented; everything here replicates structures authored by Live itself
(Live 12.4, macOS) — see [docs/als-format-notes.md](docs/als-format-notes.md)
for the full reverse-engineering write-up (parameter slots, the `KeyMidi`
block, the channel-16 macro pseudo-bus, nested-rack chaining).

## Usage

```bash
# what's in there? (tracks, racks, devices, exposed params, mappings)
python3 als_wire.py inspect "My Project.als" --track Lead

# apply a wiring spec — always backs up, writes "<name> WIRED.als" by default
python3 als_wire.py wire "My Project.als" examples/swam-funk-rig.json
```

## The spec

```json
{
  "track": "Lead",
  "macros":    {"1": "Growl", "2": "Flutter"},
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
```

| Key | Meaning |
|---|---|
| `track` | track name (EffectiveName) holding the Instrument Rack |
| `macros` | display names for the top rack's macros (1-based) |
| `midi_maps` | real MIDI mappings onto top macros: `macro: [channel (1-based), CC]` |
| `chain_nested` | auto-chain nested-rack macros up to the top rack (and copy names) |
| `devices[].plugin` | exact plugin name; applies to **every** matching device on the track |
| `params[].id` | signed-int32 host ParamID, or `juce:<internalName>` (JUCE plugins derive the ID from the name's Java hashCode — SWAM, many others) |
| `params[].macro` | macro (1-based) of the device's *innermost* enclosing rack |
| `params[].value` | initial value in the **normalized 0..1 host domain** (default 0.0 — leave at neutral unless you know the normalized value; plugin display units are NOT this domain) |

## Safety model

* the input file is **always** backed up (`<file>.bak-<timestamp>`) ;
* output goes to a **new file** by default (`--in-place` exists, still backs up) ;
* refuses to overwrite an existing mapping on any target ;
* structural validation pass after writing.

Keep your own backups anyway. Tested with Ableton Live 12.4 on macOS; other
versions may differ — the format is Ableton's to change.

## See also

* [swam-toolkit](https://github.com/Beennnn/swam-toolkit) — companion project:
  SWAM factory-mapping extractor, state decoder, parameter-ID hash, `.swamec`
  generator. The `juce:` ID scheme here comes from that work.

## License

MIT — see [LICENSE](LICENSE). As-is, no warranty; not affiliated with Ableton
or Audio Modeling.
