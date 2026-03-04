from ttsfm import TTSClient, Voice, AudioFormat

client = TTSClient()
resp = client.generate_speech(
    text="Hello from ttsfm!",
    voice=Voice.ALLOY,
    response_format=AudioFormat.MP3,
)
resp.save_to_file("hello.mp3")