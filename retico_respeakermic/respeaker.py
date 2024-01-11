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

        # below are the socket requirements

        # When the socket connects
        @sio.event
        def connect():
            print('Connected.')

        # When the socket has an error
        @sio.event
        def connect_error():
            print('Connection failed.')

        # When the socket disconnects
        @sio.event
        def disconnect():
            print('Disconnected.')

        # When the microphone sends a buffer chunk
        @sio.on('data')
        def on_data(data):
            raw_audio = data['data']
            self.audio_buffer.put(raw_audio)

        # When the microphone produces an error state
        @sio.on('error')
        def on_error(error):
            print(error)

        # After the microphone receives silence
        @sio.on('silence')
        def on_silence():
            print('Microphone is silent.')

        # After the microphone has been started
        @sio.on('startComplete')
        def on_startComplete():
            print('Started recording.')

        # After the microphone has been stopped
        @sio.on('stopComplete')
        def on_stopComplete():
            print('Stopped recording.')

        # After the microphone has been puased
        @sio.on('pauseComplete')
        def on_pauseComplete():
            print('Paused recording.')

        # After the microphone has been resumemd
        @sio.on('resumeComplete')
        def on_resumeComplete():
            print('Resumed recording.')

        # this helps keep the mic running even if retico is killed
        def shutdown_handler(sig, frame):
            sio.emit('pause')
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
        self.sio.connect('http://{}'.format(self._ip_port))

    def prepare_run(self):
        self.sio.emit('start')

    def shutdown(self):
        """Close the audio stream."""
        self.sio.emit('pause')
        self.audio_buffer = queue.Queue()