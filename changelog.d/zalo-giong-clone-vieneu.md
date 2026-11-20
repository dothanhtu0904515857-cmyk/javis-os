---
bump: minor
title: Zalo voice replies use the cloned VieNeu voice
---
## vi
### Thêm mới
- **Bot Zalo trả lời bằng giọng clone VieNeu.** Phần tiếng Việt được đọc bằng VieNeu với giọng mẫu của chủ (không tốn token, không cần internet); tiếng Anh và tiếng Trung giữ giọng riêng, ghép liền một file. Chưa cài VieNeu hoặc VieNeu lỗi thì tự rơi về giọng Google/Edge như cũ.
- Đặt giọng mẫu bằng `python server/voice_offline.py clone <file.wav>` (chép vào `<state>/tts/ref_giong.wav`) hoặc biến `JAVIS_VOICE_CLONE_REF`. Tên CREWVN được đọc là "cờ riu vi en"; từ điển riêng đặt ở `<state>/tts/pronounce.json`.

## en
### Added
- **Zalo bots answer in the cloned VieNeu voice.** Vietnamese is read by VieNeu with the owner's reference voice (no tokens, no internet); English and Chinese keep their own voices, joined into one file. If VieNeu is not installed or fails, the Google/Edge voice reads it as before.
- Set the reference voice with `python server/voice_offline.py clone <file.wav>` (copied to `<state>/tts/ref_giong.wav`) or the `JAVIS_VOICE_CLONE_REF` variable. The company name CREWVN is read as letters spelled the Vietnamese way; a custom dictionary goes in `<state>/tts/pronounce.json`.
