import os
from flask import request
from src.api.logging.TimingLogger import log_event_start
from src.utils.audio import base64_to_audio
from pydub import AudioSegment
from .common import active_connections, controller

def register_audio_events(socketio):
    @socketio.on("tango_audio_chat")
    def handleTangoAudioChat(requestBody):
        user_identifier = request.sid

        session_id = requestBody.get("session_id")
        base64_audio = requestBody.get("audio")
        tangoOrAgent = requestBody.get("tango_mode")
        
        print("Received tango_chat_user event:", session_id, tangoOrAgent)
        
        print("active_connections[user_identifier]", active_connections[user_identifier])
        tenant_id = active_connections[user_identifier]['tenant_id']
        user_id = active_connections[user_identifier]['user_id']
        client_id = active_connections[user_identifier]['client_id']
        
        # Convert the base64 audio to an audio file
        audio_file = base64_to_audio(base64_audio)
        
        # Save the audio as a temporary file
        temp_file = f"{session_id}_temp_audio.wav"
        audio = AudioSegment.from_file(audio_file)
        audio.export(temp_file, format="wav")
        
        message = controller.convertAudioToText(temp_file)
        os.remove(temp_file)
        
        print("Received tango_chat_user event:", session_id, tangoOrAgent, message)
        if tangoOrAgent == "tango":
            controller.tangoChatIO(socketio, client_id, sessionId=session_id, tenantId=tenant_id, userId=user_id, message=message, mode="audio")
