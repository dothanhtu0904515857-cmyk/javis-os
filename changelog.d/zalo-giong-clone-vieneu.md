---
bump: minor
title: Zalo voice replies use the cloned VieNeu voice
---
## vi
### Thêm mới
- **Bot Zalo trả lời bằng giọng clone VieNeu.** Phần tiếng Việt được đọc bằng VieNeu với giọng mẫu của chủ (không tốn token, không cần internet); tiếng Anh và tiếng Trung giữ giọng riêng, ghép liền một file. Chưa cài VieNeu hoặc VieNeu lỗi thì tự rơi về giọng Google/Edge như cũ.
- Đặt giọng mẫu bằng `python server/voice_offline.py clone <file.wav>` (chép vào `<state>/tts/ref_giong.wav`) hoặc biến `JAVIS_VOICE_CLONE_REF`. Tên CREWVN được đọc là "cờ riu vi en"; từ điển riêng đặt ở `<state>/tts/pronounce.json`.

- **Hỏi bằng thoại thì trả lời bằng thoại, dứt điểm.** Câu trả lời đi ra thành một tin thoại duy nhất (không kèm chữ trùng); chỉ khi tạo hoặc gửi thoại hỏng mới gửi chữ thay, nên không mất câu trả lời. Trả lời (quote) một tin nhắn thoại rồi tag bot cũng được trả lời bằng thoại. Gửi thoại hỏng một lần thì thử lại một lần.

## en
### Added
- **Zalo bots answer in the cloned VieNeu voice.** Vietnamese is read by VieNeu with the owner's reference voice (no tokens, no internet); English and Chinese keep their own voices, joined into one file. If VieNeu is not installed or fails, the Google/Edge voice reads it as before.
- Set the reference voice with `python server/voice_offline.py clone <file.wav>` (copied to `<state>/tts/ref_giong.wav`) or the `JAVIS_VOICE_CLONE_REF` variable. The company name CREWVN is read as letters spelled the Vietnamese way; a custom dictionary goes in `<state>/tts/pronounce.json`.
- **A spoken question gets one spoken answer.** The reply goes out as a single voice recording (no duplicate text); the text is sent only if the voice could not be made or sent, so no answer is lost. A reply that quotes a voice message and tags the bot is also answered by voice. A failed voice send is retried once.
