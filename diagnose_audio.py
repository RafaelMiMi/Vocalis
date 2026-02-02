import sys
import os
import time
import logging

# Configure logging to stdout
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

logger.info("Starting Audio Diagnostic...")

try:
    import sounddevice as sd
    import numpy as np
    logger.info(f"sounddevice version: {sd.__version__}")
    
    devices = sd.query_devices()
    logger.info(f"Available Devices:\n{devices}")
    
    default_input = sd.query_devices(kind='input')
    logger.info(f"Default Input Device: {default_input['name']}")

    # Test Recording
    logger.info("Attempting 3-second recording...")
    
    duration = 3
    fs = 16000
    
    def callback(indata, frames, time, status):
        if status:
            logger.warning(f"Status: {status}")
        vol = np.sqrt(np.mean(indata**2))
        if vol > 0.01:
            print(f"Audio detected! Vol: {vol:.4f}", end='\r')

    with sd.InputStream(callback=callback, channels=1, samplerate=fs):
        logger.info("InputStream active. Speak now!")
        time.sleep(duration)
        logger.info("\nRecording complete.")

    logger.info("Diagnostic passed.")

except Exception as e:
    logger.error(f"Diagnostic failed: {e}", exc_info=True)
