# Open NiederDaily Item Shortcut

The email renderer now emits `shortcuts://run-shortcut` links for:

- Calendar events
- Reminders
- On This Day photos

Create a shortcut named `Open NiederDaily Item` and sync it through iCloud so the same link works on iPhone and Mac.

## Input

The shortcut receives JSON text input. Examples:

```json
{"type":"calendar","identifier":"event-123","date":"2026-03-26","time":"5:30pm","calendar":"Little York","location":"43 West St Warwick, NY, United States","title":"UMAC pickup"}
```

```json
{"type":"reminder","identifier":"reminder-123","due":"2026-03-26","list":"Bills","title":"Submit therapy"}
```

```json
{"type":"photo","date":"2005-03-26","year":"2005","location":"Warwick, NY","filename":"IMG_1234.JPG","title":"Downtown selfie","favorite":true}
```

## Suggested Shortcut Flow

1. Get the text input.
2. Use `Get Dictionary from Input` to parse the JSON.
3. Branch on `type`.

### macOS shortcut

The easiest Mac setup is a single `Run Shell Script` action.

Use this script:

```bash
/Users/niederme/~Repos/NiederDaily/.venv/bin/python /Users/niederme/~Repos/NiederDaily/setup/open_niederdaily_item.py
```

Set:

- Shell: `/bin/zsh`
- Pass Input: `to stdin`

That helper script already knows how to:

- show the matching Calendar event
- show the matching Reminder
- spotlight the matching Photos item

### iPhone/iPad shortcut

Use `Get Dictionary from Input`, then branch by `type`.

For `calendar`:

- Use `Find Calendar Events` filtered by title and date.
- If `calendar` is present, also filter by calendar.
- Open the matched event.

For `reminder`:

- Use `Find Reminders` filtered by title and due date.
- If `list` is present, also filter by list.
- Open the matched reminder.

For `photo`:

- Use `Find Photos` filtered by date taken.
- If `filename` or `title` is available, use it to narrow the result.
- Open the matched photo in Photos.

## Notes

- The `identifier` field is included for future-proofing. On Mac the helper script can use it directly for Photos; on iPhone, title/date/list filters are the safest Shortcuts path today.
- Messages are intentionally not linked yet.
