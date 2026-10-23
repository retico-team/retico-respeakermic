
import retico_core
from retico_core.audio import AudioIU


class SpeakerSplitterModule(retico_core.AbstractModule):
    """Routes audio chunks to subscribers by the `speaker` label on each IU."""

    @staticmethod
    def name():
        return "SpeakerSplitterModule"

    @staticmethod
    def description():
        return "Routes audio to different subscribers based on the speaker label."

    @staticmethod
    def input_ius():
        return [AudioIU]

    @staticmethod
    def output_iu():
        return AudioIU

    def __init__(self, hangover=5, debug=False, debug_every=50, **kwargs):
       
        super().__init__(**kwargs)
        self.hangover = hangover
        self.debug = debug
        self.debug_every = debug_every
        self.stats = {}        # subscriber label -> {"live", "muted", "dropped"}
        self._n = 0
        self._dbg_prev = "<start>"
        self._routes = {}      # queue -> (frozenset of speakers or None, mode)
        self._last_speaker = None
        self._hold = 0

    def _label(self, q, selector):
        who = "all" if selector is None else ",".join(sorted(selector))
        return "%s[%s]" % (q.consumer.name(), who)

    def _debug_chunk(self, iu, eff):
        if eff != self._dbg_prev:
            print("[splitter] chunk %d: %s -> %s  (label=%s, doa=%s, vad=%s)" % (
                self._n, self._dbg_prev, eff, getattr(iu, "speaker", None),
                getattr(iu, "doa", None), getattr(iu, "vad", None)))
            self._dbg_prev = eff
        if self.debug_every and self._n % self.debug_every == 0:
            parts = ["%s: live=%d muted=%d dropped=%d" % (k, v["live"], v["muted"], v["dropped"])
                     for k, v in self.stats.items()]
            print("[splitter] summary @%d: %s" % (self._n, " | ".join(parts)))

    def subscribe(self, module, q=None, speaker=None, non_matching="silence"):
        
        if non_matching not in ("silence", "drop"):
            raise ValueError("non_matching must be 'silence' or 'drop'")
        if speaker is None:
            selector = None
        elif isinstance(speaker, str):
            selector = frozenset([speaker])
        else:
            selector = frozenset(speaker)
        queue_ = super().subscribe(module, q)
        self._routes[queue_] = (selector, non_matching)
        return queue_

    def _effective_speaker(self, iu):
       
        sp = getattr(iu, "speaker", None)
        if sp:
            self._last_speaker = sp
            self._hold = self.hangover
            return sp
        if self._hold > 0 and self._last_speaker:
            self._hold -= 1
            return self._last_speaker
        return None

    def _silent_copy(self, iu):
        out = self.create_iu(iu)
        out.set_audio(bytes(len(iu.raw_audio)), iu.nframes, iu.rate, iu.sample_width)
        out.doa = getattr(iu, "doa", None)
        out.vad = getattr(iu, "vad", None)
        out.speaker = getattr(iu, "speaker", None)
        out.speaker_changed = getattr(iu, "speaker_changed", False)
        out.routed_speaker = None
        out.muted = True
        return out

    def process_update(self, update_message):
        for iu, ut in update_message:
            if ut != retico_core.UpdateType.ADD:
                continue
            self._n += 1
            eff = self._effective_speaker(iu)
            iu.routed_speaker = eff
            iu.muted = False
            silent = None   # built lazily, shared by all muted subscribers

            for q in self.right_buffers():
                selector, mode = self._routes.get(q, (None, "silence"))
                st = self.stats.setdefault(self._label(q, selector),
                                           {"live": 0, "muted": 0, "dropped": 0})
                if selector is None or eff in selector:
                    out = iu
                    st["live"] += 1
                elif mode == "silence":
                    if silent is None:
                        silent = self._silent_copy(iu)
                    out = silent
                    st["muted"] += 1
                else:
                    st["dropped"] += 1
                    continue
                q.put(retico_core.UpdateMessage.from_iu(out, retico_core.UpdateType.ADD))
            if self.debug:
                self._debug_chunk(iu, eff)
        return None