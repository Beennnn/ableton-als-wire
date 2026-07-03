# How Ableton stores macro & MIDI wirings in `.als` (reverse-engineering notes)

Everything below was learned by diffing files authored by **Ableton Live 12.4
(macOS)** itself — map something in the GUI, save, gunzip, read. The format is
undocumented and may change in any Live update. Last verified: July 2026.

## The container

An `.als` is gzip-compressed UTF-8 XML. `gunzip -c project.als` gives you the
whole document. Live accepts standard re-serialized XML (attribute quoting and
self-closing style don't need to be byte-identical).

## Plugin parameter slots

Every `PluginDevice` (VST3) / `AuPluginDevice` (AU) carries a pre-allocated
list of 128 `PluginFloatParameter` slots (plus `PluginEnumParameter` for AU
enums). An **unused** slot looks like:

```xml
<PluginFloatParameter Id="0">
  <ParameterName Value="" />
  <ParameterId Value="-1" />
  <VisualIndex Value="1073741823" />
  <ParameterValue>
    <LomId Value="0" />
    <Manual Value="0" />
    <MidiControllerRange> <Min Value="0"/> <Max Value="1"/> </MidiControllerRange>
    <AutomationTarget Id="108218"> ... </AutomationTarget>
    <ModulationTarget Id="108219"> ... </ModulationTarget>
  </ParameterValue>
  ...
</PluginFloatParameter>
```

Key facts:

* `AutomationTarget`/`ModulationTarget` IDs are **already allocated** on empty
  slots — filling a slot requires no new global IDs.
* *Exposing* a parameter (what Live's **Configure** mode does) = set
  `ParameterName` (display name), `ParameterId` (the host parameter ID) and a
  sane `VisualIndex` (0, 1, 2… — `1073741823` means "unset").
* `Manual` holds the parameter's value in the **normalized 0..1 host domain**,
  not the plugin's display units.
* For **JUCE-based plugins** (SWAM, many others), the VST3 `ParameterId` is
  the Java-style `String.hashCode()` of the parameter's internal ID string
  (signed int32). Example: `growl` → `98629305`. See
  [swam-toolkit](https://github.com/Beennnn/swam-toolkit) for a generator.

## Mappings: one `KeyMidi` block, two address spaces

Both rack-macro assignments and Cmd+M MIDI mappings are stored as the same
`KeyMidi` block **inside the mapped target** (a parameter's `ParameterValue`,
or a rack's `MacroControls.N`):

```xml
<KeyMidi>
  <PersistentKeyString Value="" />
  <IsNote Value="false" />
  <Channel Value="6" />            <!-- see below -->
  <NoteOrController Value="23" />  <!-- CC number, or macro index -->
  <LowerRangeNote Value="-1" />
  <UpperRangeNote Value="-1" />
  <ControllerMapMode Value="0" />  <!-- 0 = absolute -->
</KeyMidi>
```

The `Channel` field selects the address space:

| `Channel` value | Meaning |
|---|---|
| `0`–`15` | **real MIDI mapping** (Cmd+M): 0-based channel, `NoteOrController` = CC number |
| `16` | **enclosing-rack macro bus**: `NoteOrController` = macro index (0-based, `0` = Macro 1) |

So "map this device parameter to Macro 2 of its rack" is literally
`Channel=16, NoteOrController=1` inside the parameter — and "map incoming
ch1/CC12 to this macro" is `Channel=0, NoteOrController=12` inside the
rack's `MacroControls.1`.

**Nested racks chain the same way**: a nested rack's `MacroControls.N`
carrying `Channel=16, NoteOrController=N` binds it to macro N of the *parent*
rack. The pseudo-bus always addresses the immediately enclosing rack.

## Macro names

Rack macro display names are plain attributes on the rack
(`InstrumentGroupDevice` etc.):

```xml
<MacroDisplayNames.0 Value="Growl" />
```

Default value is `Macro 1` … `Macro 16`; anything else shows as a custom name.

## Plugin state (bonus)

`ProcessorState` (VST3) holds the plugin's own state as hex. For SWAM
instruments that blob contains a plain XML document (`VC2!` magic followed by
`<swam …>`), which lets you read the *plugin-domain* value of every parameter
without opening the GUI — see `decode_state.py` in swam-toolkit. Careful:
plugin-domain values are **not** the normalized values `Manual` expects.

## Verification status

| Technique | Status |
|---|---|
| slot filling + `Channel=16` param→macro | ✅ format taken from Live-authored files |
| real MIDI maps (`Channel=0..15`) | ✅ format matches 12 pre-existing Cmd+M mappings in a real project |
| nested-rack macro chaining | ⚠️ inferred from the same mechanism — in-DAW load test pending |
| bulk-generated projects load in Live | ⚠️ structural validation done; final in-DAW validation pending |
