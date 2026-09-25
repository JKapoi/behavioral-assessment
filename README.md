# behavioral-assessment
Behavioral assessment shiny application

## Emailing results

After completing the assessment, participants can email themselves their report (text summary plus
the section-totals chart) from the Results page. The button only appears when SMTP is configured
through environment variables:

| Variable | Purpose |
| --- | --- |
| `SMTP_HOST` | SMTP server, e.g. `smtp.gmail.com` |
| `SMTP_PORT` | Default `587` (STARTTLS); `465` for SSL |
| `SMTP_USER` / `SMTP_PASSWORD` | Login (for Gmail use an App Password) |
| `SMTP_FROM` | Sender address (defaults to `SMTP_USER`) |
| `SMTP_BCC` | Optional comma-separated addresses that receive a copy (e.g. the facilitator) |
| `SMTP_STARTTLS` | Set to `0` to skip STARTTLS (local test servers only) |

On shinyapps.io / Posit Connect, set these as environment variables in the app settings.
