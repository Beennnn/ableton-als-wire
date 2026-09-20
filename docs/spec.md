# The wiring spec, key by key

A spec is a JSON object describing what to wire on **one track**. Pass it to
`als_wire.py wire`. A complete nine-instrument example lives in
[`../examples/swam-funk-rig.json`](../examples/swam-funk-rig.json).

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
| `track` | track name (`EffectiveName`) holding the Instrument Rack |
| `macros` | display names for the top rack's macros (1-based) |
| `midi_maps` | real MIDI mappings onto top macros: `macro: [channel (1-based), CC]` |
| `chain_nested` | auto-chain nested-rack macros up to the top rack (and copy their names) |
| `devices[].plugin` | exact plugin name; applies to **every** matching device on the track |
| `params[].name` | the display name the parameter gets in Live |
| `params[].id` | signed-int32 host ParamID, or `juce:<internalName>` |
| `params[].macro` | macro (1-based) of the device's *innermost* enclosing rack |
| `params[].value` | initial value in the normalized 0..1 host domain (default `0.0`) |

## `params[].id` — the `juce:` shorthand

JUCE plugins derive the host parameter ID from the parameter's internal name via
Java's `String.hashCode()`, so `juce:growl` resolves to that hash at wire time.
This covers SWAM and many other JUCE-based plugins. Anything else: pass the
signed 32-bit integer the DAW itself stores.

See [swam-toolkit](https://github.com/Beennnn/swam-toolkit) for how the scheme was
established and for a resolver you can run on any name.

## `params[].value` — the normalized domain

The value is in the **normalized 0..1 host domain**, not the units the plugin
displays. Leave it at the `0.0` default unless you know the normalized value for
what you want.

## `params[].macro` — which rack a macro belongs to

The macro number refers to the *innermost* rack enclosing that device, which on a
nested setup is not the rack whose macros you see at the top of the track. Setting
`chain_nested` to `true` is what then links those inner macros up to the top rack,
copying their names on the way, so one top-level knob moves every instrument.
