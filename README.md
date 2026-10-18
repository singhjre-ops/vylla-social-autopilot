# Vylla Social Autopilot

Writes and designs social media posts for Jaskaran Singh, Vylla Home, and schedules them through Metricool's free plan.

**Every Saturday:**
1. Gemini writes next week's posts. Each post follows the theme calendar in `config.yaml` and covers a town from one of three regions: Greater Danbury and New Milford, lower Fairfield County, and New Haven County.
2. A compliance check blocks fair-housing red flags. It retries up to 3 times. A post that is still flagged is imported as a draft for you to fix.
3. Each post gets a Vylla-branded graphic and a 10-second vertical video.
4. Images and videos are published to a public web folder (GitHub Pages), so Metricool can fetch them.
5. You receive a Metricool CSV on Telegram.
6. Import the CSV in Metricool: **Planning → Calendar → options menu → Import CSV**. It takes about 2 minutes a week. Review or edit the posts in the calendar; Metricool posts them on schedule.

The brokerage name, phone and "Equal Housing Opportunity" are added to every caption and graphic automatically.

## Default weekly schedule (stays under 20 posts a month)

| Day | Networks | Media |
|---|---|---|
| Monday | Facebook, Instagram (Reel), TikTok, YouTube (Short) | video |
| Tuesday | Google Business Profile | image (Google Business Profile does not take video) |
| Wednesday | Facebook, Instagram, TikTok, YouTube | video |
| Friday | Facebook, Instagram, TikTok, YouTube | video |

That's 17–20 posts a month if Metricool counts one post per row. The exporter tracks a running count in `data/metricool_ledger.json` and skips days rather than go over `monthly_post_limit`.

**Check this once:**
1. In Metricool, schedule one post to two networks.
2. See whether your remaining monthly count drops by 1 or by 2.
3. If it drops by 2, set `count_mode: per_network` in `config.yaml`.

With per-network counting, the free plan covers only about 5 posts a month. Each one goes to 4 networks.

## Monthly cost

| Item | Cost |
|---|---|
| Gemini API, free tier | $0 |
| Metricool free plan | $0 |
| GitHub Actions and GitHub Pages (public repository) | $0 |
| Telegram | $0 |
| **Total** | **$0** |

## One-time setup

1. **Gemini key:** go to https://aistudio.google.com/apikey and create a free key.
2. **Telegram bot** (it delivers the weekly CSV):
   - In Telegram, message `@BotFather`, send `/newbot`, and copy the token.
   - Send any message to your new bot.
   - Open `https://api.telegram.org/bot<TOKEN>/getUpdates` and copy `chat.id`.
3. **Metricool template:**
   - In Metricool, go to Calendar → Import CSV and download the template.
   - Save it as `data/metricool_template.csv`.
   - The exporter then uses Metricool's exact column names. Without it, it uses a best-guess English header.
4. **GitHub:**
   - Create a **public** repository named `vylla-social-autopilot` and push this folder to it.
   - Free GitHub Pages needs a public repository. No keys are stored in the code; they live in GitHub's encrypted secrets.
   - Under Settings → Pages, choose "Deploy from a branch", branch `main`, folder `/docs`.
   - In `config.yaml`, replace `YOUR-GITHUB-USERNAME` in `media_base_url` with your GitHub username.
   - Under Settings → Secrets and variables → Actions, add `GEMINI_API_KEY`, `TELEGRAM_BOT_TOKEN` and `TELEGRAM_CHAT_ID`.
5. **Test:** under Actions → Metricool weekly batch → Run workflow. The CSV arrives on Telegram, and it's also attached to the workflow run.

For the first few weeks, consider setting `import_as_draft: true`. Posts then land in Metricool as drafts, and you confirm each one.

## Data you keep current

- **`data/listings.csv`:** your own active Smart MLS listings, one row each.
  - Only rows with `status` set to `Active` and `seller_consent` set to `yes` get posted.
  - If `smart_mls_agent_id` is set in the config, rows must also match it.
  - Each listing is posted once.
- **`data/market_stats.csv`:** monthly town figures from Smart MLS market reports.
  - Market-update posts use only these numbers.
  - With no data, that day becomes a town spotlight. The AI never makes up statistics.

## Local commands

```bash
cp .env.example .env    # fill in keys
python3 -m venv .venv && .venv/bin/pip install -r requirements.txt
.venv/bin/python -m autopilot.main week --sample   # test without a Gemini key
.venv/bin/python -m autopilot.main week            # build next week's CSV in exports/
```

The video needs `ffmpeg`. GitHub Actions installs it automatically. On a Mac, install it with `brew install ffmpeg`.

## Daily API posting (optional, paid)

The code can also post daily with no weekly import, through Zernio (about $6 per account a month) or Ayrshare (about $149 a month):
1. Set `publisher: zernio` and add `ZERNIO_API_KEY`.
2. Uncomment the schedule in `.github/workflows/autopilot.yml`.
3. Disable the Metricool weekly workflow.

Daily mode sends each draft to Telegram with Approve and Skip buttons. Set `approval_required: false` to skip that step. Posts with compliance flags still wait for you.

Vylla's brand guide says marketing materials need marketing-department approval. Confirm with Vylla before you post without review.
