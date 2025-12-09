import requests

url = "http://localhost:8000/api/stt/transcribe"
file_path = r"C:\Users\user\Documents\Sound Recordings\Recording (19).m4a"

with open(file_path, "rb") as f:
    files = {"file": ("recording.m4a", f, "audio/mp4")}
    data = {"language": "en"}
    resp = requests.post(url, files=files, data=data)

print("Status:", resp.status_code)
print("Body:", resp.text)
