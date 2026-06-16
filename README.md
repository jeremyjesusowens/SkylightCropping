# SkylightCropping

Crop photos to **16:9** widescreen using Claude vision to detect the subject and keep it in frame — no dumb centre-crops.

## How it works

1. Each image is sent to the Claude API (vision).
2. Claude returns the focal point as `(x%, y%)` — the coordinates of the most important subject.
3. The script computes the largest 16:9 rectangle that keeps that point as centred as possible, clamped to the image edges.
4. The cropped image is saved (original is untouched).

## Running the desktop app (Windows)

**First time only:**
1. Install [Python 3.11+](https://python.org/downloads) for Windows (check "Add Python to PATH")
2. Install dependencies: double-click `build.bat` — or in a terminal:
   ```
   pip install -r requirements.txt
   ```
3. Launch the app:
   ```
   python app.py
   ```

**Building a standalone `.exe`** (no Python required on target machine):
```
build.bat
```
The executable is created at `dist\SkylightCropping.exe`.

### In-app setup

Open the **Settings** tab and fill in:

| Field | What to enter |
|---|---|
| Anthropic API Key | From [console.anthropic.com](https://console.anthropic.com) → API Keys |
| Yahoo App Password | [myaccount.yahoo.com](https://myaccount.yahoo.com) → Security → App passwords |
| From Email | Your Yahoo address |
| To Email | Pre-filled with `your-skylight-frame@example.com` |

Click **Save Settings**. No environment variables needed.

---

## Command-line usage (advanced)

Requires `ANTHROPIC_API_KEY` environment variable.

The tool has two subcommands: `crop` and `send`.

### Cropping

```bash
# Single file
python smart_crop.py crop photo.jpg

# Multiple files / entire directory
python smart_crop.py crop photos/ -o cropped/

# Custom suffix (default: _16x9)
python smart_crop.py crop photo.jpg --suffix _wide

# Preview crop boxes without writing files
python smart_crop.py crop photos/ --dry-run

# Use a different Claude model
python smart_crop.py crop photos/ --model claude-sonnet-4-6
```

Output files are saved next to the originals with `_16x9` appended (e.g. `sunset.jpg` → `sunset_16x9.jpg`), unless `--output-dir` is set. If Claude cannot determine a focal point for an image, that photo is skipped and reported in the failure summary — there is no silent fallback to centre-cropping.

#### Crop options

| Flag | Description |
|---|---|
| `-o / --output-dir DIR` | Write output files to `DIR` |
| `--suffix TEXT` | Suffix before extension (default: `_16x9`) |
| `--model MODEL` | Claude model ID (default: `claude-opus-4-7`) |
| `--dry-run` | Print crop boxes without writing files |

### Sending photos by email

Sends each photo in a directory as an individual email via **Yahoo Mail** (free).

**Prerequisites:** Generate a Yahoo App Password — Yahoo does not allow third-party apps to use your regular account password.

1. Go to [myaccount.yahoo.com](https://myaccount.yahoo.com) → **Security** → **App passwords**
2. Click **Generate app password**, name it (e.g. "Skylight"), and copy the 16-character password
3. Set it as an environment variable:

```bash
export SMTP_PASSWORD="your-16-char-app-password"
```

Then send:

```bash
# Send all photos in a directory
python smart_crop.py send cropped/ --from you@yahoo.com

# Override the recipient (default: your-skylight-frame@example.com)
python smart_crop.py send cropped/ --from you@yahoo.com --to other@example.com
```

Any photos that fail to send are reported in a summary at the end.

#### Send options

| Flag | Description |
|---|---|
| `--from ADDRESS` | Your Yahoo email address **(required)** |
| `--to ADDRESS` | Recipient (default: `your-skylight-frame@example.com`) |
| `--smtp-host HOST` | SMTP host (default: `smtp.mail.yahoo.com`) |
| `--smtp-port PORT` | SMTP port (default: `587`) |
| `--smtp-password PW` | App password (prefer `SMTP_PASSWORD` env var) |

## Supported formats

JPEG, PNG, WebP, GIF.
