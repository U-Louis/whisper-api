# Bounds evidence

Command: ./scripts/collect-evidence.sh

Versions:
3.11.18
openai-whisper 20240930

Statuses:
missing 401
unknown 401
oversize 413
toolong 422
unreadable 422
busy 429
busy-first 200
speech 200

Bodies (refusals only):
missing {"error":"unauthorized"}
unknown {"error":"unauthorized"}
oversize {"error":"payload_too_large"}
toolong {"error":"too_long"}
unreadable {"error":"unreadable_audio"}
busy {"error":"busy"}

Speech body:
{"text":"This is a short test.","language":"en"}
