"""DOA-based online speaker diarization for the ReSpeaker retico pipeline.

Expects AudioIUs that carry `doa` (degrees) and `vad` attributes, as produced
by RespeakerMicrophoneModule. Place this module directly after the mic module
(before any module that rebuilds AudioIUs and would drop those attributes).

Output: the same audio, passed through, with these attributes on each IU:
    iu.doa              angle from the mic module (unchanged)
    iu.vad              vad flag from the mic module (unchanged)
    iu.speaker          "speaker1", "speaker2", ... while voiced, else None
    iu.speaker_changed  True on the first chunk after the speaker switches
"""
import math

import retico_core
from retico_core.audio import AudioIU


def circ_diff(a, b):
    """Signed difference a - b on a circle, in (-180, 180]."""
    return (a - b + 180.0) % 360.0 - 180.0


def circ_mean(angles):
    s = sum(math.sin(math.radians(a)) for a in angles)
    c = sum(math.cos(math.radians(a)) for a in angles)
    return math.degrees(math.atan2(s, c)) % 360.0


class DOADiarizer:
    """Pure-Python online diarizer (no retico dependency).

    known_speakers: optional {"speaker1": 330, "speaker2": 180} start angles.
    max_speakers:   total speakers allowed, including known ones.
    tolerance:      max angular distance (deg) to match a speaker centroid.
    min_new_chunks: consecutive unmatched, mutually consistent voiced chunks
                    needed before a new speaker is created.
    min_switch_chunks: consecutive voiced chunks needed before the active
                    speaker switches (smooths jittery DOA).
    adapt:          if True, centroids drift toward new observations.
    """

    def __init__(self, known_speakers=None, max_speakers=4, tolerance=30.0,
                 min_new_chunks=8, min_switch_chunks=3, adapt=True,
                 adapt_rate=0.05):
        self.centroids = dict(known_speakers or {})
        self.max_speakers = max_speakers
        self.tolerance = tolerance
        self.min_new_chunks = min_new_chunks
        self.min_switch_chunks = min_switch_chunks
        self.adapt = adapt
        self.adapt_rate = adapt_rate

        self.current = None
        self._cand = None
        self._cand_streak = 0
        self._pending = []

    def _match(self, angle):
        best, best_d = None, None
        for name, c in self.centroids.items():
            d = abs(circ_diff(angle, c))
            if best_d is None or d < best_d:
                best, best_d = name, d
        return best, best_d

    def _classify(self, angle):
        """Return a speaker label for this angle, or None if undecided."""
        best, d = self._match(angle)
        if best is not None and d <= self.tolerance:
            self._pending = []
            if self.adapt:
                self.centroids[best] = (
                    self.centroids[best]
                    + self.adapt_rate * circ_diff(angle, self.centroids[best])
                ) % 360.0
            return best

        if len(self.centroids) >= self.max_speakers:
            return best  # forced to nearest existing speaker

        # Unmatched: collect evidence for a new speaker.
        if self._pending and abs(circ_diff(angle, circ_mean(self._pending))) > self.tolerance:
            self._pending = []
        self._pending.append(angle)
        if len(self._pending) >= self.min_new_chunks:
            name = "speaker%d" % (len(self.centroids) + 1)
            self.centroids[name] = circ_mean(self._pending)
            self._pending = []
            return name
        return None

    def update(self, angle, vad):
        """Process one chunk. Returns (speaker_label_or_None, changed)."""
        if angle is None or not vad:
            self._cand, self._cand_streak = None, 0
            return None, False

        label = self._classify(angle % 360.0)
        if label is None:
            # undecided: keep reporting the current speaker
            return self.current, False

        if label == self.current:
            self._cand, self._cand_streak = None, 0
            return self.current, False

        if self.current is None:
            self.current = label
            return self.current, True

        if label == self._cand:
            self._cand_streak += 1
        else:
            self._cand, self._cand_streak = label, 1
        if self._cand_streak >= self.min_switch_chunks:
            self.current = label
            self._cand, self._cand_streak = None, 0
            return self.current, True
        return self.current, False


class DOADiarizationModule(retico_core.AbstractModule):
    """Retico wrapper around DOADiarizer. Passes audio through with labels."""

    @staticmethod
    def name():
        return "DOADiarizationModule"

    @staticmethod
    def description():
        return "Labels audio chunks with a speaker based on ReSpeaker DOA."

    @staticmethod
    def input_ius():
        return [AudioIU]

    @staticmethod
    def output_iu():
        return AudioIU

    def __init__(self, known_speakers=None, max_speakers=4, tolerance=30.0,
                 min_new_chunks=8, min_switch_chunks=3, adapt=True, **kwargs):
        super().__init__(**kwargs)
        self.diarizer = DOADiarizer(
            known_speakers=known_speakers,
            max_speakers=max_speakers,
            tolerance=tolerance,
            min_new_chunks=min_new_chunks,
            min_switch_chunks=min_switch_chunks,
            adapt=adapt,
        )

    def process_update(self, update_message):
        out = retico_core.UpdateMessage()
        produced = False
        for iu, ut in update_message:
            if ut != retico_core.UpdateType.ADD:
                continue
            doa = getattr(iu, "doa", None)
            vad = getattr(iu, "vad", None)
            speaker, changed = self.diarizer.update(doa, bool(vad))

            new_iu = self.create_iu(iu)
            new_iu.set_audio(iu.raw_audio, iu.nframes, iu.rate, iu.sample_width)
            new_iu.doa = doa
            new_iu.vad = vad
            new_iu.speaker = speaker
            new_iu.speaker_changed = changed
            out.add_iu(new_iu, retico_core.UpdateType.ADD)
            produced = True
        return out if produced else None