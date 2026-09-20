# als-wire

**Expose plugin parameters, map them to rack macros and MIDI-map those macros —
in batch, by editing an Ableton Live `.als` file directly. No GUI clicking.**

```console
$ python3 als_wire.py inspect "Funk Rig.als" --track Lead
track [MidiTrack] 'Lead': 10 rack(s), 9 plugin device(s)
  rack: macros named=[(0, 'Growl'), (1, 'Flutter')] mapped=[(0, '0', '12'), (1, '0', '13')]

$ python3 als_wire.py wire "Funk Rig.als" examples/swam-funk-rig.json
SWAM Trumpet [PluginDevice]: 2 param(s) exposed (nested rack)
SWAM Tenor Sax 3 [PluginDevice]: 2 param(s) exposed (nested rack)
…
chained macros [1, 2] of 9 nested rack(s) to the top rack
top macro 1 <- MIDI ch1/CC12
top macro 2 <- MIDI ch1/CC13

wrote  : Funk Rig WIRED.als
backup : Funk Rig.als.bak-20260703-184122
```

## What it's for

In Live, exposing a plugin parameter and mapping it to a macro is a
Configure-mode + right-click round trip, **per parameter, per device**. Sixty of
those — nine SWAM instruments in nested racks, two macros each, plus the MIDI
mapping — is an afternoon of mouse work that has to be redone the next time the
rack changes.

## Install

```bash
git clone https://github.com/Beennnn/als-wire.git
cd als-wire && python3 als_wire.py inspect "Some Project.als"
```

Python 3, standard library only — nothing to install.

## Commands

| | |
|---|---|
| `inspect PROJECT.als [--track NAME]` | tracks, racks, devices, exposed params, MIDI mappings |
| `swam PROJECT.als [--track NAME]` | decode each SWAM device's internal state (velocity / expression / CC) — diagnoses a silent chain |
| `wire PROJECT.als SPEC.json [--out OUT.als \| --in-place]` | apply a wiring spec |

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

Every key is documented in **[docs/spec.md](docs/spec.md)**; a full nine-instrument
spec is in [`examples/swam-funk-rig.json`](examples/swam-funk-rig.json).

## Safety

The input file is **always** backed up (`<file>.bak-<timestamp>`), output goes to a
**new file** by default, an existing mapping on a target is never overwritten, and
the result is re-parsed and structurally checked after writing. Keep your own
backups anyway.

## Unofficial

The `.als` format is undocumented. Everything written here replicates structures
authored by Live itself (Live 12.4, macOS) — the reverse-engineering write-up is in
[docs/als-format-notes.md](docs/als-format-notes.md): parameter slots, the `KeyMidi`
block, the channel-16 macro pseudo-bus, nested-rack chaining. Other Live versions
may differ; the format is Ableton's to change.

## See also

[swam-toolkit](https://github.com/Beennnn/swam-toolkit) — companion project: SWAM
factory-mapping extractor, state decoder, parameter-ID hash, `.swamec` generator.
The `juce:` ID scheme here comes from that work. Both were announced in this
[KVR Audio thread](https://www.kvraudio.com/forum/viewtopic.php?t=631399).

## Credits

Built by Benoît Besson in an AI-assisted workflow: a substantial part of the format
archaeology, tooling and documentation was produced together with
[Claude](https://claude.com/claude-code) (Anthropic). The wiring structures were
learned from projects authored by Ableton Live itself and validated on a real
live-rig project.

## License

MIT — see [LICENSE](LICENSE). As-is, no warranty; not affiliated with Ableton or
Audio Modeling.
