

import base64
import io
import os

def base64_to_audio(base64_audio):
    audio_data = base64.b64decode(base64_audio)
    audio_file = io.BytesIO(audio_data)
    return audio_file