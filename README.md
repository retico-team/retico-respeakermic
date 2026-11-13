# retico-respeakermic
A ReTiCo module that allows the use of a Seeed ReSpeaker as a microphone. Besides the audio, it uses the ReSpeaker's direction of arrival (DOA) to tell speakers apart and route each speaker's audio separately.

## Installation and Requirements

To use the ReSpeaker modules you first need to install the retico-respeakermic package:
* Install retico-respeakermic:
```pip install retico-respeakermic```

  or, for the latest development version from GitHub:
```pip install git+https://github.com/retico-team/retico-respeakermic.git```

The ReSpeaker has to run the `robot-mic` server, which streams the audio to the module:

1. Connect to the ReSpeaker using ssh:
``` bash
ssh respeaker@192.168.0.169 # for the gray respeaker
# OR
ssh respeaker@192.168.0.167 # for the blue respeaker
```
2. Start the server on the ReSpeaker:
``` bash
cd robot-mic/
npm start
```

## Modules

### `RespeakerMicrophoneModule`
Produces `AudioIU`s with the audio streamed from the ReSpeaker; it doesn't subscribe to any IUs. Each IU also has a `doa` attribute (the direction of arrival in degrees) and a `vad` attribute (whether voice activity was detected).

#### Arguments:
* `respeaker_ip_port` (str): the IP address and port of the ReSpeaker's server, e.g. `"192.168.0.167:8000"`
* `chunk_size` (int): the number of frames in each `AudioIU`; defaults to `5000`
* `rate` (int): the sample rate of the audio; defaults to `44100`
* `sample_width` (int): the width of a single sample in bytes; defaults to `2`

### `DOADiarizationModule`
Subscribes to `AudioIU` and outputs `AudioIU`. It labels each chunk of audio with a speaker based on its DOA, and passes the audio through with a `speaker` attribute (`"speaker1"`, `"speaker2"`, … while someone is speaking, otherwise `None`) and a `speaker_changed` attribute (`True` on the first chunk after the speaker switches). It needs the `doa` and `vad` attributes, so it has to subscribe directly to `RespeakerMicrophoneModule`.

#### Arguments:
* `known_speakers` (dict): the starting angle of each known speaker, e.g. `{"speaker1": 240, "speaker2": 60}`; defaults to `None`
* `max_speakers` (int): the total number of speakers allowed, including the known ones; defaults to `4`
* `tolerance` (float): the maximum distance in degrees from a speaker's angle to count as that speaker; defaults to `30.0`
* `min_new_chunks` (int): the number of consecutive unmatched chunks needed before a new speaker is created; defaults to `8`
* `min_switch_chunks` (int): the number of consecutive chunks needed before the active speaker switches; defaults to `3`
* `adapt` (bool): if `True`, each speaker's angle drifts toward new observations; defaults to `True`

### `SpeakerTracker`
Subscribes to `AudioIU` from `DOADiarizationModule` and keeps the most recent speaker in `current_speaker` (`None` during silence) and the most recent angle in `current_doa`. It takes no arguments.

### `SpeakerSplitterModule`
Subscribes to `AudioIU` from `DOADiarizationModule` and outputs `AudioIU`, routing the audio to its subscribers by speaker. Choose the speakers each subscriber receives with `subscribe(module, speaker=..., non_matching=...)`:
* `speaker` (str or list): the speaker or speakers to send to this subscriber; if `None`, it receives all audio
* `non_matching` (str): `"silence"` sends silence in place of other speakers' audio, `"drop"` sends nothing; defaults to `"silence"`

#### Arguments:
* `hangover` (int): the number of chunks to keep routing to the last speaker after their label drops out; defaults to `5`
* `debug` (bool): if `True`, prints routing changes and statistics; defaults to `False`
* `debug_every` (int): how often, in chunks, the statistics are printed; defaults to `50`

### Example 1
**Note:** The example uses `DebugModule` from `retico_core` and `GoogleASRModule` from [retico-googleasr](https://github.com/retico-team/retico-googleasr) (`pip install retico-googleasr`).

```python
from retico_core import network
from retico_core.debug import DebugModule
from retico_googleasr import GoogleASRModule
from retico_respeakermic import RespeakerMicrophoneModule, DOADiarizationModule, SpeakerSplitterModule


mic = RespeakerMicrophoneModule("192.168.0.167:8000", rate=16000, sample_width=2) # 192.168.0.167 for the blue respeaker, 192.168.0.169 for the gray respeaker
doa = DOADiarizationModule(known_speakers={"speaker1": 240, "speaker2": 60}, max_speakers=2, adapt=False) # angles: 60, 150, 240, 330
splitter = SpeakerSplitterModule(hangover=5)
asr = GoogleASRModule("en-US", rate=16000)
debug = DebugModule(print_payload_only=True)

mic.subscribe(doa)
doa.subscribe(splitter)
splitter.subscribe(asr, speaker=["speaker1", "speaker2"])
asr.subscribe(debug)

network.run(mic)

input()

network.stop(mic)
```

### Example 2
**Note:** This example is the lab's runner. It prints the current speaker with `SpeakerTracker`, and sends each speaker to `GoogleASRModule` from [retico-googleasr](https://github.com/retico-team/retico-googleasr) (`pip install retico-googleasr`) on its own subscription.

```python
import time
from retico_core import network, UpdateType
from retico_core.debug import CallbackModule
from retico_googleasr import GoogleASRModule
from retico_respeakermic import RespeakerMicrophoneModule, DOADiarizationModule, SpeakerTracker, SpeakerSplitterModule

msg = []

def callback(update_msg):
    global msg
    for x, ut in update_msg:
        if ut == UpdateType.ADD:
            msg.append(x)
        if ut == UpdateType.REVOKE:
            msg.remove(x)
    txt = ""
    committed = False
    for x in msg:
        txt += x.text + " "
        committed = committed or x.committed
    print(" " * 80, end="\r")
    print(f"{txt}", end="\r")
    if committed:
        msg = []
        print("")


mic = RespeakerMicrophoneModule("192.168.0.167:8000", rate=16000, sample_width=2) # 192.168.0.167 for the blue respeaker, 192.168.0.169 for the gray respeaker
googleasr = GoogleASRModule("en-US", rate=16000)
debug = CallbackModule(callback=callback)
doa = DOADiarizationModule(known_speakers={"speaker1": 240, "speaker2": 60}, max_speakers=2, adapt=False) # angles: 60, 150, 240, 330
tracker = SpeakerTracker()
splitter = SpeakerSplitterModule(hangover=5)

mic.subscribe(doa)
doa.subscribe(splitter)
doa.subscribe(tracker)
splitter.subscribe(googleasr, speaker="speaker1")
splitter.subscribe(googleasr, speaker="speaker2")
googleasr.subscribe(debug)

network.run(mic)
try:
    last = object()
    while True:
        speaker = tracker.current_speaker
        if speaker != last:
            print(speaker, ": ")
            last = speaker
        time.sleep(0.1)
except KeyboardInterrupt:
    pass
finally:
    network.stop(mic)
```
