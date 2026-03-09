from pydantic import BaseModel
from fastapi import APIRouter, HTTPException
from engine.src.plugin_system.plugin import Plugin
from engine.src.editor.editor_session import EditorSession

from engine.src.services.tts_service import TtsService

class TTSRequest(BaseModel):
    text: str
    speed: float = 1.0  # Kokoro uses float 0.25 - 4.0

class TTSPlugin(Plugin):
    def __init__(self):
        self.tts_service = TtsService()
        self.tts_service.prewarm()

    @property
    def name(self) -> str:
        return "TTS"

    @property
    def version(self) -> str:
        return "1.0.0"

    def register_routes(self, router: APIRouter, session: EditorSession) -> None:

        @router.post("/play")
        def play_text(payload: TTSRequest):
            """Sends text to the local TTS engine."""
            if not payload.text:
                raise HTTPException(status_code=400, detail="No text provided.")
            try:
                self.tts_service.speed = payload.speed
                self.tts_service.speak(payload.text)
                return {"status": "success", "message": "Playback started."}
            except Exception as e:
                raise HTTPException(status_code=500, detail=str(e))

        @router.post("/stop")
        def stop_playback():
            """Stops the current TTS playback."""
            try:
                self.tts_service.stop()
                return {"status": "success", "message": "Playback stopped."}
            except Exception as e:
                raise HTTPException(status_code=500, detail=str(e))

        @router.post("/pause")
        def pause_resume_playback():
            """Toggles pause/resume on the current TTS playback."""
            try:
                self.tts_service.toggle_pause()
                is_paused = self.tts_service.is_paused
                return {
                    "status": "success",
                    "paused": is_paused,
                    "message": "Paused." if is_paused else "Resumed.",
                }
            except Exception as e:
                raise HTTPException(status_code=500, detail=str(e))