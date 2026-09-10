import sys, os
from retico import *
from retico_core import *

os.environ['RESPEAKER'] = 'retico-respeakermic'
os.environ['RETICO'] = 'retico-core'
os.environ['GOOGLEASR'] = 'retico-googleasr'

sys.path.append(os.environ['RESPEAKER'])
sys.path.append(os.environ['RETICO'])
sys.path.append(os.environ['GOOGLEASR'])

from retico_core.debug import DebugModule
from retico_googleasr.googleasr import GoogleASRModule
from retico_respeakermic.respeaker import RespeakerMicrophoneModule

m1 = RespeakerMicrophoneModule("192.168.0.167:8000", rate=44100, sample_width=2)
m2 = GoogleASRModule("en-US")
m3 = DebugModule()

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
