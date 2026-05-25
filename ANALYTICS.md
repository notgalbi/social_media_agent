# Captionly — Analytics Event Map

Self-hosted analytics via SQLite (`backend/analytics.db`). Dashboard at `/analytics?key=<ANALYTICS_KEY>`.

---

## Funnel Overview

```
App Open
  └─► File Upload
        └─► Generate Start
              ├─► Generate Success
              │     └─► Caption Select
              │           └─► Post Open  ──► [Instagram opened]
              │           └─► Draft Save ──► [Calendar pinned]
              └─► Generate Error
```

---

## Events Reference

### Session & Entry

| Event | Trigger | Key Props |
|-------|---------|-----------|
| `app_open` | Page load, before `enterApp()` | `has_username` |
| `instagram_connect_start` | Tap "Connect Instagram" button | — |
| `tab_switch` | Tap any bottom tab button | `tab` (create / drafts / settings) |

---

### Create Flow

| Event | Trigger | Key Props |
|-------|---------|-----------|
| `file_upload` | Files added via drop zone or file picker | `count`, `has_video` |
| `tone_select` | Tap a vibe pill (only on activate, not deactivate) | `tone` |
| `genre_select` | Tap a genre pill (only on activate, not "auto") | `genre` |
| `generate_start` | Tap "Generate Captions" | `tones`, `genres`, `length` (1–5), `hashtags` (0–5), `file_count` |
| `generate_success` | AI response received and parsed | `level` (length_level) |
| `generate_error` | Network error or server error | `error` (first 80 chars of message) |
| `caption_select` | Tap a caption card (not on silent auto-select) | `index` (0 / 1 / 2) |
| `music_preview` | Tap ▶ on a music card | `artist`, `song` |
| `post_open` | Tap "Post to Instagram" (caption already copied) | — |

---

### Draft & Calendar Flow

| Event | Trigger | Key Props |
|-------|---------|-----------|
| `draft_save` | Tap "Save Draft" | — |
| `draft_schedule` | Set or remove a calendar pin date on a draft | `date` (YYYY-MM-DD or "removed") |
| `day_detail_open` | Tap a calendar day with drafts | `date`, `count` |
| `day_detail_open_draft` | Tap "Open →" inside day detail panel | — |

---

### Settings & Appearance

| Event | Trigger | Key Props |
|-------|---------|-----------|
| `theme_change` | Tap a theme swatch (Rose / Carbon / Forest) | `theme` |

---

## Button → Event Map

| Button / Element | Event Fired |
|-----------------|-------------|
| "Try it now →" (welcome screen) | *(no event — leads to enterApp)* |
| "Connect Instagram" | `instagram_connect_start` |
| File drop zone / file picker | `file_upload` |
| Vibe pill | `tone_select` |
| Genre pill | `genre_select` |
| "Generate Captions" | `generate_start` |
| Caption card | `caption_select` |
| ▶ on music card | `music_preview` |
| "Post to Instagram" | `post_open` |
| "Save Draft" | `draft_save` |
| 📅 schedule button on draft card | `draft_schedule` (on date picker change) |
| Calendar day with dot | `day_detail_open` |
| "Open →" in day detail sheet | `day_detail_open_draft` |
| Create / Drafts / Settings tab | `tab_switch` |
| Theme swatch | `theme_change` |

---

## Funnel Step Definitions

| Step | Event | Goal |
|------|-------|------|
| 1. Activated | `app_open` | User reached the app |
| 2. Engaged | `file_upload` | User uploaded content |
| 3. Attempted | `generate_start` | User requested AI generation |
| 4. Generated | `generate_success` | AI returned captions |
| 5. Selected | `caption_select` | User chose a caption |
| 6. Converted | `post_open` | User tapped Post (caption copied) |

Conversion rate = `post_open` sessions / `app_open` sessions.

---

## Querying the Data

```sql
-- Funnel step counts (last 30 days)
SELECT event, COUNT(DISTINCT session) as sessions
FROM events
WHERE ts > datetime('now', '-30 days')
  AND event IN ('app_open','file_upload','generate_start','generate_success','caption_select','post_open')
GROUP BY event;

-- Most popular tones
SELECT json_extract(props,'$.tone') as tone, COUNT(*) as cnt
FROM events WHERE event = 'tone_select'
GROUP BY tone ORDER BY cnt DESC;

-- Theme distribution
SELECT json_extract(props,'$.theme') as theme, COUNT(DISTINCT session) as sessions
FROM events WHERE event = 'theme_change'
GROUP BY theme ORDER BY sessions DESC;

-- Error breakdown
SELECT json_extract(props,'$.error') as error, COUNT(*) as cnt
FROM events WHERE event = 'generate_error'
GROUP BY error ORDER BY cnt DESC LIMIT 20;
```

---

*Last updated: 2026-05-11 — added draft_schedule, day_detail_open, day_detail_open_draft events and theme_change event.*
