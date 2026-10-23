import retico_core
from retico_core.audio import AudioIU

class SpeakerSplitterModule(retico_core.AbstractModule):

    @staticmethod
    def name():
        return "SpeakerSplitterModule"
    
    @staticmethod
    def description():
        return "Routes audio to different subscribeers based on label"
    
    @staticmethod
    def input_ius():
        return [AudioIU]
    
    @staticmethod
    def output_iu():
        return AudioIU
    
    def __init__(self, hangover=5, **kwargs):
        super().__init__(**kwargs)
        self.hangover = hangover
        self._routes = {}

        self.last_speaker = None
        self._hold = 0

    def subscribe(self, module, q=None, speaker=None, no_match="silence"):
        if no_match not in ("silence", "drop"):
            raise ValueError("no_match must be 'silence' or 'drop'")
        if speaker is None:
            selector = None
        elif isinstance(speaker, str):
            selector = frozenset([speaker])
        else:
            selector = frozenset(speaker)
        queue_ = super().subscribe(module, q)
        self._routes[queue_] = (selector, no_match)
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
    
    def _silent_copy(self,iu):
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
            eff = self._effective_speaker(iu)
            iu.routed_speaker = eff
            iu.muted = False
            silent = None

            for q in self.right_buffers():
                selector, mode = self._routes.get(q, (None, "silence"))
                if selector is None or eff in selector:
                    out = iu
                elif mode == "silence":
                    if silent is None:
                        silent = self._silent_copy(iu)
                    out = silent
                else:
                    continue
                q.put(retico_core.UpdateMessage.from_iu(out, retico_core.UpdateType.ADD))

                return None
