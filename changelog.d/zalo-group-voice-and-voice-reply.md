---
bump: minor
title: Zalo bot hears voice messages in groups and can answer by voice
---
## vi
### Thêm mới
- **Bot Zalo nghe được tin thoại trong nhóm.** Gửi tin thoại rồi nhắn "@bot nhận xét giúp em", bot nghe đúng tin thoại của người vừa gọi và trả lời. Trước đây tin thoại trong nhóm bị bỏ qua nên bot báo chưa nghe được.
- **Bot trả lời lại bằng giọng nói.** Tin thoại được trả lời bằng chữ kèm một file mp3 bấm vào là nghe. Chữ Hán trong câu trả lời được đọc bằng giọng Trung, phần còn lại bằng giọng Việt.

### Sửa lỗi
- **Công tắc trả lời bằng giọng nói của bot Zalo hoạt động trở lại.** Cài đặt này từng bị mất sau một lần cập nhật.

## en
### Added
- **The Zalo bot hears voice messages in groups.** Send a voice message, then "@bot please review": the bot hears the voice message of the person who called it and answers. Group voice messages used to be dropped, so the bot said it could not hear.
- **The bot answers by voice.** A voice message gets a text answer plus an mp3 you tap to play. Chinese characters in the answer are read by a Chinese voice, the rest by the Vietnamese one.

### Fixed
- **The Zalo bot's voice reply switch works again.** The setting had been lost in an update.
