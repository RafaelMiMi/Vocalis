import numpy as np
import sounddevice as sd
import logging

logger = logging.getLogger(__name__)

class SoundManager:
    def __init__(self, sample_rate=44100):
        self.sample_rate = sample_rate

    def _generate_tone(self, frequency, duration, volume=0.5):
        t = np.linspace(0, duration, int(self.sample_rate * duration), False)
        # Sine wave with fade in/out to avoid clicks
        tone = np.sin(frequency * t * 2 * np.pi)
        
        # Envelope
        envelope = np.ones_like(tone)
        fade_len = int(self.sample_rate * 0.01) # 10ms fade
        if fade_len > 0 and fade_len * 2 < len(envelope):
             envelope[:fade_len] = np.linspace(0, 1, fade_len)
             envelope[-fade_len:] = np.linspace(1, 0, fade_len)
             
        return (tone * envelope * volume).astype(np.float32)

    def play_start(self):
        # High "Ping"
        try:
            wave = self._generate_tone(880, 0.15, 0.3)
            sd.play(wave, self.sample_rate)
        except Exception as e:
            logger.debug(f"Sound error: {e}")

    def play_stop(self):
        # Low "Pong"
        try:
            wave = self._generate_tone(440, 0.15, 0.3)
            sd.play(wave, self.sample_rate)
        except Exception as e:
             logger.debug(f"Sound error: {e}")

    def play_success(self):
        # Ascending chord (Major triad)
        try:
            dur = 0.1
            c = self._generate_tone(523.25, dur, 0.2)
            e = self._generate_tone(659.25, dur, 0.2)
            g = self._generate_tone(783.99, dur * 2, 0.2)
            full = np.concatenate([c, e, g])
            sd.play(full, self.sample_rate)
        except Exception as e:
             logger.debug(f"Sound error: {e}")
            
    def play_error(self):
        # Descending buzz
        try:
            wave = self._generate_tone(150, 0.3, 0.4)
            sd.play(wave, self.sample_rate)
        except:
            pass
