import sys, os
from retico import *
from retico_core import *

os.environ['RESPEAKER'] = 'retico-respeakermic'
os.environ['RETICO'] = 'retico-core'
os.environ['GOOGLEASR'] = 'retico-googleasr'

sys.path.append(os.environ['RESPEAKER'])
sys.path.append(os.environ['RETICO'])
sys.path.append(os.environ['GOOGLEASR'])

from retico_core.debug import CallbackModule
from retico_googleasr.googleasr import GoogleASRModule
from retico_respeakermic.respeaker import RespeakerMicrophoneModule
from retico_respeakermic.doadiarization import DOADiarizationModule, SpeakerTracker
from retico_respeakermic.splitter import SpeakerSplitterModule

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
doa = DOADiarizationModule(known_speakers={"speaker1": 240, "speaker2": 60}, max_speakers=2, adapt=False) # speaker1: 240, speaker2: 60, speaker3: 120, speaker4: 300
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
