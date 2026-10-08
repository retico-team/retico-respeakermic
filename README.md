# retico-respeakermic
A ReTiCo module that allows the use of a Seeed ReSpeaker as a microphone
## Runner Example for Respeaker:
``` python
import sys, os
from retico import *
from retico_core import *

os.environ['RESPEAKER'] = 'retico-respeakermic'
os.environ['RETICO'] = 'retico-core'
os.environ['GOOGLEASR'] = 'retico-googleasr'
os.environ['WHISPER'] = 'retico-whisperasr'

sys.path.append(os.environ['RESPEAKER'])
sys.path.append(os.environ['RETICO'])
sys.path.append(os.environ['GOOGLEASR'])
sys.path.append(os.environ['WHISPER'])

from retico_core.debug import DebugModule, CallbackModule
from retico_googleasr.googleasr import GoogleASRModule
from retico_respeakermic.respeaker import RespeakerMicrophoneModule
from retico_whisperasr.whisperasr import WhisperASRModule

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

m1 = RespeakerMicrophoneModule("192.168.0.169:8000", rate=44100, sample_width=2)
m2 = GoogleASRModule()
m3 = CallbackModule(callback=callback)


m1.subscribe(m2)
m2.subscribe(m3)

m1.run()
m2.run()
m3.run()


print("Running")
input()

m1.stop()
m2.stop()
m3.stop()
```

## Runner Example for DOA Diarization:
``` python
import sys, os
from retico import *
from retico_core import *

os.environ['RESPEAKER'] = 'retico-respeakermic'
os.environ['RETICO'] = 'retico-core'
os.environ['GOOGLEASR'] = 'retico-googleasr'
os.environ['WHISPER'] = 'retico-whisperasr'

sys.path.append(os.environ['RESPEAKER'])
sys.path.append(os.environ['RETICO'])
sys.path.append(os.environ['GOOGLEASR'])
sys.path.append(os.environ['WHISPER'])

from retico_core.debug import DebugModule, CallbackModule
from retico_googleasr.googleasr import GoogleASRModule
from retico_respeakermic.respeaker import RespeakerMicrophoneModule
from retico_respeakermic.doadiarization import DOADiarizationModule, SpeakerTracker
from retico_whisperasr.whisperasr import WhisperASRModule

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

mic = RespeakerMicrophoneModule("192.168.0.169:8000", rate=44100, sample_width=2)
m2 = GoogleASRModule()
m3 = CallbackModule(callback=callback)
m4 = DOADiarizationModule(known_speakers={"speaker1": 330, "speaker2": 180}, adapt=False)
tracker = SpeakerTracker()

mic.subscribe(m4)         
m4.subscribe(tracker)          

network.run(mic)
try:
    last = object()
    while True:
        speaker = tracker.current_speaker
        if speaker != last:
            print("Speaker:", speaker or "(silence)", "| doa:", tracker.current_doa)
            last = speaker
        time.sleep(0.1)
except KeyboardInterrupt:
    pass
finally:
    network.stop(mic)

```