# Smoke Test Checklist (manual)

Run this against the **baseline** (before any change) and again after every step in Phases 1-2.
Behavior must match. Record results in the table at the bottom.

Use a SHORT video (2-3 min) so runs are fast. Keep the same test video every time.

| # | Check | How | Expected |
|---|---|---|---|
| 1 | Sign up | Create a new account | "Account created", redirected to login |
| 2 | Log in | Log in with it | Lands on dashboard, display name shown |
| 3 | Analyze YouTube (English) | Paste the test URL, language = english | Progress stages appear; title, summary, action items, decisions, questions, category all produced |
| 4 | Results tab | Open Results | 5 tabs populated; TXT export downloads |
| 5 | Chat Q&A | Ask "what is this video about?" and one specific question | Sensible answers, no errors |
| 6 | Timestamp citation | Ask "when did they mention <something specific>?" | Answer includes a [MM:SS] timestamp |
| 7 | Frame grab | Ask "show me the frame at 0:30" | Image appears in chat |
| 8 | Quiz | Type "generate quiz", pick 5 | 5 questions; submit shows a score |
| 9 | Notes | Type "generate notes" | Notes render; PDF downloads and opens |
| 10 | Hinglish | Analyze a short Hindi/Hinglish clip, language = hinglish | English transcript + summary produced |
| 11 | Local file | Paste a path to a local .mp4/.mp3 | Analysis completes |
| 12 | History | Open History | New entries listed with source + snippet |
| 13 | Stats | Open Stats | Charts render |
| 14 | Recent chats | Sidebar Recent -> click an old chat | Chat and results restored; asking a question still works |
| 15 | New Chat / Delete | Start a New Chat; delete a chat via the menu | Behaves normally |
| 16 | Log out / in | Log out, log in | Data still there |

## Results log

| Date | Version / step | Passed | Failed (numbers) | Notes |
|---|---|---|---|---|
| | baseline-v0 | | | |