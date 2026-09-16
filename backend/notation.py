from __future__ import annotations

from dataclasses import dataclass, asdict
from html import escape
from math import floor
from threading import RLock
from typing import Any

QUANTIZE_GRIDS = {
    "1/4": 1.0,
    "1/8": 0.5,
    "1/16": 0.25,
    "1/32": 0.125,
}

# Prefer flat spellings for flat project keys. This is intentionally a small,
# deterministic first pass; enharmonic/contextual spelling can later be an
# optional notation extension without changing raw captured MIDI.
SHARP_NAMES = ("C", "C#", "D", "D#", "E", "F", "F#", "G", "G#", "A", "A#", "B")
FLAT_NAMES = ("C", "Db", "D", "Eb", "E", "F", "Gb", "G", "Ab", "A", "Bb", "B")
FLAT_KEYS = {"F", "Bb", "Eb", "Ab", "Db", "Gb", "Cb", "Fm", "Bbm", "Ebm", "Abm"}


def clamp(value: float, low: float, high: float) -> float:
    return max(low, min(high, value))


def quantize_beats(beats: float, grid: str) -> float:
    step = QUANTIZE_GRIDS.get(grid)
    if step is None:
        raise ValueError(f"quantize must be one of {sorted(QUANTIZE_GRIDS)}")
    # Match native std::round semantics for non-negative beat positions so
    # bridge and native implementations agree exactly at half-grid ties.
    return floor(max(0.0, beats) / step + 0.5) * step


def midi_pitch_name(pitch: int, key: str) -> tuple[str, int, int]:
    if pitch < 0 or pitch > 127:
        raise ValueError("pitch must be 0..127")
    names = FLAT_NAMES if key in FLAT_KEYS or "b" in key else SHARP_NAMES
    token = names[pitch % 12]
    octave = pitch // 12 - 1
    if len(token) == 1:
        return token, octave, 0
    accidental = -1 if "b" in token else 1
    return token[0], octave, accidental


@dataclass
class NotationSettings:
    enabled: bool = True
    source: str = "midi"
    quantize: str = "1/16"
    preserve_performance: bool = True
    spell_by_project_key: bool = True

    def patch(self, data: dict[str, Any]) -> None:
        if "enabled" in data:
            self.enabled = bool(data["enabled"])
        if "source" in data:
            source = str(data["source"]).strip().lower()
            if source not in {"midi", "manual"}:
                raise ValueError("notation source must be midi or manual")
            self.source = source
        if "quantize" in data:
            grid = str(data["quantize"]).strip()
            if grid not in QUANTIZE_GRIDS:
                raise ValueError(f"quantize must be one of {sorted(QUANTIZE_GRIDS)}")
            self.quantize = grid
        if "preservePerformance" in data:
            if not bool(data["preservePerformance"]):
                raise ValueError("preservePerformance must remain true in notation v1")
            self.preserve_performance = True
        if "spellByProjectKey" in data:
            self.spell_by_project_key = bool(data["spellByProjectKey"])


@dataclass
class CapturedNote:
    id: int
    pitch: int
    velocity: int
    raw_start_seconds: float
    raw_end_seconds: float
    raw_start_beats: float
    raw_duration_beats: float


class NotationPart:
    """Player-scoped raw performance capture plus derived notation view."""

    def __init__(self, player_id: str, snapshot: dict[str, Any] | None = None) -> None:
        self.player_id = player_id
        self.settings = NotationSettings()
        self._notes: list[CapturedNote] = []
        self._active: dict[int, list[tuple[int, int, float, float]]] = {}
        self._next_id = 1
        if snapshot:
            self._restore(snapshot)

    def _restore(self, snapshot: dict[str, Any]) -> None:
        settings = snapshot.get("settings") or {}
        self.settings.patch(settings)
        highest = 0
        for raw in snapshot.get("rawNotes") or []:
            try:
                note = CapturedNote(
                    id=max(1, int(raw["id"])),
                    pitch=int(raw["pitch"]),
                    velocity=int(raw.get("velocity", 100)),
                    raw_start_seconds=max(0.0, float(raw["rawStartSeconds"])),
                    raw_end_seconds=max(0.0, float(raw["rawEndSeconds"])),
                    raw_start_beats=max(0.0, float(raw.get("rawStartBeats", 0.0))),
                    raw_duration_beats=max(0.0, float(raw.get("rawDurationBeats", 0.0))),
                )
            except (KeyError, TypeError, ValueError):
                continue
            if 0 <= note.pitch <= 127 and note.raw_end_seconds >= note.raw_start_seconds:
                self._notes.append(note)
                highest = max(highest, note.id)
        self._next_id = highest + 1

    def note_on(self, pitch: int, velocity: int, seconds: float, bpm: float) -> None:
        if pitch < 0 or pitch > 127:
            raise ValueError("pitch must be 0..127")
        velocity = int(clamp(float(velocity), 1.0, 127.0))
        seconds = max(0.0, float(seconds))
        beat = seconds * float(bpm) / 60.0
        note_id = self._next_id
        self._next_id += 1
        self._active.setdefault(pitch, []).append((note_id, velocity, seconds, beat))

    def note_off(self, pitch: int, seconds: float, bpm: float) -> None:
        if pitch < 0 or pitch > 127:
            raise ValueError("pitch must be 0..127")
        active = self._active.get(pitch)
        if not active:
            raise ValueError(f"no active note for pitch {pitch}")
        note_id, velocity, start_seconds, start_beat = active.pop(0)
        if not active:
            self._active.pop(pitch, None)
        end_seconds = max(start_seconds, float(seconds))
        end_beat = end_seconds * float(bpm) / 60.0
        duration = max(0.0, end_beat - start_beat)
        self._notes.append(CapturedNote(
            id=note_id,
            pitch=pitch,
            velocity=velocity,
            raw_start_seconds=start_seconds,
            raw_end_seconds=end_seconds,
            raw_start_beats=start_beat,
            raw_duration_beats=duration,
        ))
        self._notes.sort(key=lambda item: (item.raw_start_seconds, item.id))
        if len(self._notes) > 4096:
            del self._notes[:-4096]

    def clear(self) -> None:
        self._notes.clear()
        self._active.clear()
        self._next_id = 1

    def derived_notes(self, key: str) -> list[dict[str, Any]]:
        result: list[dict[str, Any]] = []
        minimum_duration = QUANTIZE_GRIDS[self.settings.quantize]
        for note in self._notes:
            start = quantize_beats(note.raw_start_beats, self.settings.quantize)
            duration = max(minimum_duration, quantize_beats(note.raw_duration_beats, self.settings.quantize))
            step, octave, alter = midi_pitch_name(note.pitch, key if self.settings.spell_by_project_key else "C")
            result.append({
                "id": note.id,
                "pitch": note.pitch,
                "velocity": note.velocity,
                "rawStartSeconds": round(note.raw_start_seconds, 6),
                "rawEndSeconds": round(note.raw_end_seconds, 6),
                "rawStartBeats": round(note.raw_start_beats, 6),
                "rawDurationBeats": round(note.raw_duration_beats, 6),
                "startBeats": round(start, 6),
                "durationBeats": round(duration, 6),
                "step": step,
                "alter": alter,
                "octave": octave,
                "name": f"{step}{'#' if alter > 0 else 'b' if alter < 0 else ''}{octave}",
            })
        return result

    def snapshot(self, key: str, include_raw: bool = True, note_limit: int | None = None) -> dict[str, Any]:
        derived = self.derived_notes(key)
        if note_limit is not None:
            derived = derived[-max(0, int(note_limit)):]
        result = {
            "playerId": self.player_id,
            "settings": {
                "enabled": self.settings.enabled,
                "source": self.settings.source,
                "quantize": self.settings.quantize,
                "preservePerformance": self.settings.preserve_performance,
                "spellByProjectKey": self.settings.spell_by_project_key,
            },
            "activeNotes": sum(len(items) for items in self._active.values()),
            "rawNoteCount": len(self._notes),
            "notes": derived,
        }
        if include_raw:
            result["rawNotes"] = [{
                "id": n.id,
                "pitch": n.pitch,
                "velocity": n.velocity,
                "rawStartSeconds": round(n.raw_start_seconds, 6),
                "rawEndSeconds": round(n.raw_end_seconds, 6),
                "rawStartBeats": round(n.raw_start_beats, 6),
                "rawDurationBeats": round(n.raw_duration_beats, 6),
            } for n in self._notes]
        return result

    def musicxml(self, part_name: str, bpm: float, key: str) -> str:
        notes = self.derived_notes(key)
        divisions = 8
        # One measure at 4/4 = 32 divisions. Basic first export favors
        # interoperability over engraving sophistication.
        measure_length = divisions * 4
        measures: dict[int, list[dict[str, Any]]] = {}
        for note in notes:
            measure = int(floor(note["startBeats"] / 4.0)) + 1
            measures.setdefault(measure, []).append(note)
        if not measures:
            measures[1] = []

        fifths_by_key = {"C":0,"G":1,"D":2,"A":3,"E":4,"B":5,"F#":6,"C#":7,
                         "F":-1,"Bb":-2,"Eb":-3,"Ab":-4,"Db":-5,"Gb":-6,"Cb":-7}
        fifths = fifths_by_key.get(key, 0)
        lines = [
            '<?xml version="1.0" encoding="UTF-8" standalone="no"?>',
            '<!DOCTYPE score-partwise PUBLIC "-//Recordare//DTD MusicXML 4.0 Partwise//EN" "http://www.musicxml.org/dtds/partwise.dtd">',
            '<score-partwise version="4.0">',
            '  <part-list>',
            f'    <score-part id="P1"><part-name>{escape(part_name)}</part-name></score-part>',
            '  </part-list>',
            '  <part id="P1">',
        ]
        for measure_no in range(1, max(measures) + 1):
            lines.append(f'    <measure number="{measure_no}">')
            if measure_no == 1:
                lines.extend([
                    '      <attributes>',
                    f'        <divisions>{divisions}</divisions>',
                    f'        <key><fifths>{fifths}</fifths></key>',
                    '        <time><beats>4</beats><beat-type>4</beat-type></time>',
                    '        <clef><sign>G</sign><line>2</line></clef>',
                    '      </attributes>',
                    f'      <direction placement="above"><sound tempo="{float(bpm):g}"/></direction>',
                ])
            measure_notes = sorted(measures.get(measure_no, []), key=lambda n: (n["startBeats"], n["pitch"]))
            cursor = (measure_no - 1) * 4.0
            last_start: float | None = None
            for note in measure_notes:
                chord = last_start is not None and abs(note["startBeats"] - last_start) < 1e-9
                gap = 0.0 if chord else max(0.0, note["startBeats"] - cursor)
                if gap > 1e-9:
                    rest_duration = max(1, int(round(gap * divisions)))
                    lines.extend([
                        '      <note>', '        <rest/>', f'        <duration>{rest_duration}</duration>', '      </note>'
                    ])
                    cursor += rest_duration / divisions
                duration = max(1, int(round(note["durationBeats"] * divisions)))
                pitch_lines = [f'          <step>{note["step"]}</step>']
                if note["alter"]:
                    pitch_lines.append(f'          <alter>{note["alter"]}</alter>')
                pitch_lines.append(f'          <octave>{note["octave"]}</octave>')
                body = ['      <note>']
                if chord:
                    body.append('        <chord/>')
                body.extend(['        <pitch>', *pitch_lines, '        </pitch>', f'        <duration>{duration}</duration>', '      </note>'])
                lines.extend(body)
                if not chord:
                    cursor = max(cursor, note["startBeats"] + note["durationBeats"])
                last_start = note["startBeats"]
            remaining = measure_no * 4.0 - cursor
            if remaining > 1e-9:
                duration = max(1, int(round(remaining * divisions)))
                lines.extend(['      <note>', '        <rest/>', f'        <duration>{duration}</duration>', '      </note>'])
            lines.append('    </measure>')
        lines.extend(['  </part>', '</score-partwise>', ''])
        return "\n".join(lines)


class NotationRegistry:
    def __init__(self, player_ids: list[str], snapshot: dict[str, Any] | None = None) -> None:
        self._lock = RLock()
        snapshot = snapshot or {}
        self._parts = {pid: NotationPart(pid, snapshot.get(pid)) for pid in player_ids}

    def ensure(self, player_id: str) -> NotationPart:
        with self._lock:
            return self._parts.setdefault(player_id, NotationPart(player_id))

    def snapshot(self, key: str, include_raw: bool = True, note_limit: int | None = None) -> dict[str, Any]:
        with self._lock:
            return {pid: part.snapshot(key, include_raw=include_raw, note_limit=note_limit) for pid, part in self._parts.items()}

    def part_snapshot(self, player_id: str, key: str, include_raw: bool = True, note_limit: int | None = None) -> dict[str, Any]:
        with self._lock:
            return self.ensure(player_id).snapshot(key, include_raw=include_raw, note_limit=note_limit)

    def patch_settings(self, player_id: str, data: dict[str, Any]) -> None:
        with self._lock:
            self.ensure(player_id).settings.patch(data)

    def note(self, player_id: str, action: str, pitch: int, velocity: int, seconds: float, bpm: float) -> None:
        with self._lock:
            part = self.ensure(player_id)
            action = action.strip().lower()
            if action == "on":
                part.note_on(int(pitch), int(velocity), seconds, bpm)
            elif action == "off":
                part.note_off(int(pitch), seconds, bpm)
            else:
                raise ValueError("notation note action must be on or off")

    def clear(self, player_id: str) -> None:
        with self._lock:
            self.ensure(player_id).clear()

    def musicxml(self, player_id: str, part_name: str, bpm: float, key: str) -> str:
        with self._lock:
            return self.ensure(player_id).musicxml(part_name, bpm, key)
