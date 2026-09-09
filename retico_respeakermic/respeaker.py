import base64
import retico_core
from retico_core.audio import AudioIU

import socketio
import signal
import queue
import sys


class RespeakerMicrophoneModule(retico_core.AbstractProducingModule):
    """A module that produces IUs containing audio signals that are captures by
    a microphone."""

    @staticmethod
    def name():
        return "RespeakerMicrophoneModule"

    @staticmethod
    def description():
        return "A prodicing module that records audio from a seeed respeaker microphone array."

    @staticmethod
    def output_iu():
        return AudioIU

    def __init__(self, respeaker_ip_port, chunk_size=5000, rate=44100, sample_width=2, **kwargs):
        """
        Initialize the Microphone Module.

        Args:
            chunk_size (int): The number of frames that should be stored in one
                AudioIU
            rate (int): The frame rate of the recording
            sample_width (int): The width of a single sample of audio in bytes.
        """
        super().__init__(**kwargs)
        self.chunk_size = chunk_size
        self.rate = rate
        self.sample_width = sample_width
        self._ip_port = respeaker_ip_port
        sio = socketio.Client()
        self.sio = sio
        self.audio_buffer = queue.Queue()
        self._logged_type = False

        # below are the socket requirements

        # When the socket connects
        @sio.event(namespace='/mic')
        def connect():
            print('Connected.')

        # When the socket has an error
        @sio.event(namespace='/mic')
        def connect_error():
            print('Connection failed.')

        # When the socket disconnects
        @sio.event(namespace='/mic')
        def disconnect():
            print('Disconnected.')

        # When the microphone sends a buffer chunk
        @sio.on('data', namespace='/mic')
        def on_data(data):
            raw_audio = data['data']

            if not self._logged_type:
                print(f"[respeaker] raw_audio arrives as: {type(raw_audio)}")
                self._logged_type = True

            if isinstance(raw_audio, (bytes, bytearray)):
                pass  # already correct
            elif isinstance(raw_audio, dict) and raw_audio.get('type') == 'Buffer':
                raw_audio = bytes(raw_audio['data'])
            elif isinstance(raw_audio, str):
                raw_audio = base64.b64decode(raw_audio)
            elif isinstance(raw_audio, list):
                raw_audio = bytes(raw_audio)
            else:
                print(f"[respeaker] unrecognized audio chunk type {type(raw_audio)}, dropping")
                return

            self.audio_buffer.put(raw_audio)

        # When the microphone produces an error state
        @sio.on('error', namespace='/mic')
        def on_error(error):
            print(error)

        # After the microphone receives silence
        @sio.on('silence', namespace='/mic')
        def on_silence():
            print('Microphone is silent.')

        # After the microphone has been started
        @sio.on('startComplete', namespace='/mic')
        def on_startComplete():
            print('Started recording.')

        # After the microphone has been stopped
        @sio.on('stopComplete', namespace='/mic')
        def on_stopComplete():
            print('Stopped recording.')

        # After the microphone has been puased
        @sio.on('pauseComplete', namespace='/mic')
        def on_pauseComplete():
            print('Paused recording.')

        # After the microphone has been resumemd
        @sio.on('resumeComplete', namespace='/mic')
        def on_resumeComplete():
            print('Resumed recording.')

        # this helps keep the mic running even if retico is killed
        def shutdown_handler(sig, frame):
            sio.emit('pause', namespace='/mic')
            sio.disconnect()
            sys.exit(0)

        signal.signal(signal.SIGINT, shutdown_handler)

    def process_update(self, input_iu):
        if not self.audio_buffer:
            return None
        sample = self.audio_buffer.get()
        output_iu = self.create_iu()
        output_iu.set_audio(sample, self.chunk_size, self.rate, self.sample_width)
        return retico_core.UpdateMessage.from_iu(output_iu, retico_core.UpdateType.ADD)

    def setup(self):
        """Set up the socket for recording."""
        self.sio.connect('http://{}'.format(self._ip_port), namespaces=['/mic'], transports=['polling', 'websocket'])

    def prepare_run(self):
        self.sio.emit('start', namespace='/mic')

    def shutdown(self):
        """Close the audio stream."""
        self.sio.emit('pause', namespace='/mic')
        self.audio_buffer = queue.Queue()
