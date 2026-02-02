import sounddevice as sd
import soundfile as sf
import numpy as np
import threading
import tempfile
import os
import queue
import logging

logger = logging.getLogger(__name__)

class AudioRecorder:
    def __init__(self, sample_rate=16000, channels=1, device_index=None):
        self.sample_rate = sample_rate
        self.channels = channels
        self.device_index = device_index
        self.recording = False
        self.stop_event = threading.Event()
        self.audio_queue = queue.Queue()

    def record_once(self, max_duration=30, stream_callback=None) -> str:
        """
        Records audio until stop() is called or max_duration is reached.
        Returns the path to the temporary .wav file.
        stream_callback: Optional function(indata) to receive live audio chunks (numpy array).
        """
        self.stop_event.clear()
        self.recording = True
        
        # Create a temporary file
        temp_file = tempfile.NamedTemporaryFile(suffix=".wav", delete=False)
        temp_path = temp_file.name
        temp_file.close()

        logger.info(f"Starting recording to {temp_path}")

        try:
            with sf.SoundFile(temp_path, mode='w', samplerate=self.sample_rate, 
                              channels=self.channels, subtype='PCM_16') as file:
                def callback(indata, frames, time, status):
                    if status:
                        logger.warning(f"Audio status: {status}")
                    self.audio_queue.put(indata.copy())

                logger.info("Opening InputStream...")
                with sd.InputStream(samplerate=self.sample_rate, device=self.device_index,
                                    channels=self.channels, callback=callback):
                    logger.info("InputStream open. Starting loop.")
                    
                    import time
                    start_ts = time.time()
                    
                    while not self.stop_event.is_set():
                        try:
                            # Get data from queue
                            data = self.audio_queue.get(timeout=0.1)
                            file.write(data)
                            if stream_callback:
                                stream_callback(data)
                        except queue.Empty:
                            # Periodic log to show we are alive
                            # logger.debug("Queue empty...")
                            pass
                        
                        if time.time() - start_ts > max_duration:
                            logger.info("Max duration reached")
                            break
                    logger.info("Stop event set. Exiting loop.")
                            
        except Exception as e:
            logger.error(f"Recording failed: {e}")
            os.unlink(temp_path)
            raise
        finally:
            self.recording = False
            self.stop_event.set()

        logger.info(f"Recording finished: {temp_path}")
        return temp_path

    def stop(self):
        self.stop_event.set()
