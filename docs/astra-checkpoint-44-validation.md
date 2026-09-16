# Astra backlog checkpoint 44 validation

Checkpoint 44 adds explicitly armed unicast sACN/E1.31 output and moves portable lighting authoring above raw universe/channel coordinates by resolving semantic fixture intent through the active venue patch.

## Native lighting network

- Added allocation-free E1.31 data-packet encoding for one full 512-slot DMX universe.
- Added an explicitly armed unicast UDP sACN adapter on the standard 5568 port; configuration alone cannot transmit.
- The native engine selects exactly one lighting network protocol at a time. Reconfiguration disarms both Art-Net and sACN before the new target is installed.
- sACN uses a process-unique CID, independent per-universe sequence counters and a configurable E1.31 `universeBase` covering the existing 16 bounded internal universes.
- Existing raw DMX scheduling and Art-Net behavior remain backward compatible.

## Semantic venue lighting

The committed `lighting.primary` venue patch may now carry execution details such as:

```json
{
  "protocol": "sacn",
  "target": "127.0.0.1",
  "port": 5568,
  "universeBase": 101,
  "fixtures": {
    "front-wash-left": {
      "universe": 0,
      "address": 17,
      "parameters": {
        "intensity": 0,
        "red": 1,
        "green": 2,
        "blue": 3
      }
    }
  }
}
```

`POST /api/v1/lighting/schedule` can continue to accept raw `universe`/`channel`/`value`, or it can accept `fixtureId`, `parameter` and `normalizedValue`. Semantic requests are resolved only through the active venue patch; unmapped fixtures/parameters, out-of-range normalized values and mappings beyond DMX channel 512 fail closed.

Parameter mappings may also declare a bounded output range and inversion. The show-facing semantic identity remains portable while universe/channel details remain venue-local.

## Capability and UI changes

- `lighting-sacn` is now an implemented adapter capability with the same explicit-arm boundary as Art-Net.
- Show compatibility requirements follow the desired lighting protocol and accept the other network protocol as an equivalent venue adaptation when available.
- The operator UI can persist Art-Net or sACN, target/port and sACN universe base. Saving remains non-authoritative; physical output still requires a separate arm acknowledgement.
- Added `lighting-fixture-map.schema.json`; show-state lighting network now publishes `universeBase`.

## Validation

- Fresh RT-qualified native build: 2/2 CTest targets passed.
- Release Python suite against the fresh RT engine: 533 tests passed with zero skips.
- Automation performance: passed with 4096 points / 8192 frames and binary block-entry search.
- Public JSON schemas: 118 parsed successfully.
- `frontend/openapi.json`: parsed successfully as OpenAPI 3.1.0.
- Frontend JavaScript: 7/7 files passed `node --check`.
- Focused venue/state/native/API integration group passed, including E1.31 packet fields, explicit arm behavior, sACN network execution and semantic fixture resolution through a committed venue adaptation.

The one-shot clean release wrapper reached the tool execution timeout after its fresh Release/RT build and 2/2 CTest pass while its Python phase was still running. The remaining release steps were therefore run separately against the same RT-qualified source state; the complete split gate above passed.

## Remaining boundary

This checkpoint does not claim multicast sACN discovery, E1.31 synchronization packets, RDM/fixture discovery, physical console interoperability or venue-network timing qualification. The fixture map is explicit venue configuration, not automatic fixture personality discovery. Physical lighting authority remains transient and independently fenced from venue adaptation.
