# Workflow: Deliver Newsletter

## Objective
Send the final HTML newsletter to one or more recipients via Resend, then save a delivery receipt.

## Required Inputs
| Input | Source |
|---|---|
| `html_path` | Output of `assemble_newsletter.md` |
| `recipient` | User-provided email address |
| `subject` | From `content_<slug>.json["subject"]` or user override |
| `from_addr` | Optional override (default: `Newsletter <newsletter@resend.dev>`) |
| `slug` | Derived from topic |
| `date_prefix` | `YYYY-MM-DD` |

## Pre-flight Checks
1. Confirm `RESEND_API_KEY` is set in `.env`
2. Confirm `resend` Python package is installed (`pip install resend`)
3. Confirm `html_path` file exists and is non-empty
4. If sending to a non-Resend domain, confirm the domain is verified in the Resend dashboard

## Steps

### 1. Send the newsletter
```bash
cd NewsLetterDemo
python tools/send_newsletter.py \
  --html <html_path> \
  --to <recipient> \
  --subject "<subject>" \
  --from "<from_addr>" \
  --receipt .tmp/receipts/<date_prefix>_<slug>.json
```

### 2. Verify delivery
Read the receipt JSON:
- `resend_response.id` should be present (this is the Resend message ID)
- No `error` key in the response

If delivery fails:
| Error | Action |
|---|---|
| `401 Unauthorized` | Check `RESEND_API_KEY` in `.env` |
| `422 Unprocessable` | Check `from` domain is verified in Resend dashboard |
| `429 Rate limit` | Wait 60 seconds, retry once |
| Other error | Read full error message, check Resend docs |

### 3. Archive receipt
Copy receipt JSON to `archive/<date_prefix>_<slug>/receipt.json`.

### 4. Report
Return to calling workflow with:
- Resend message ID
- Timestamp sent
- Recipient

## Notes
- **Free Resend tier**: 100 emails/day, 3,000/month. No credit card required.
- **Custom domains**: To send from your own domain, add and verify it in the Resend dashboard, then use `--from "Newsletter <newsletter@yourdomain.com>"`
- **Testing**: Use Resend's test mode by sending to the recipient address provided by Resend in your dashboard (you@resend.dev by default on free accounts)
- **HTML compatibility**: Use `--inline-css` in `generate_html.py` before sending to maximize email client compatibility
