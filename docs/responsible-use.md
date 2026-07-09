# Responsible use

This project demonstrates an event-aggregation pipeline: source adapters →
normalization → classification → filtering → deduplication → ranking → digest
delivery. It ships with all external sources **disabled by default** and runs
offline on sample fixtures.

Fetching data from third-party websites is your responsibility. Before you enable
any live source, make sure your usage is lawful and fair.

## Before enabling a source

- **Read the terms of service** of each website and confirm automated access is allowed.
- **Respect `robots.txt`** and any documented crawl policies.
- **Do not bypass** CAPTCHAs, paywalls, login walls or access controls.
- **Only enable sources you are authorized to use.**

## When running live

- Keep **reasonable rate limits** and run infrequently (e.g. once a day at most).
- Store only **basic factual metadata** (title, date, city, venue, price, a link
  back to the source). Do not copy full descriptions, images or promotional media.
- **Link back** to the original event page.
- Do not reproduce or redistribute a substantial part of any source's event
  database. In the EU, systematic extraction/re-use of a structured database may
  engage database (sui generis) rights independently of copyright.

## What the demo does

The default quick-start reads `fixtures/sample_events.json` and never touches the
network. Continuous integration runs the same offline demo on every push. Enabling
live extraction is an explicit, opt-in step that you configure and are accountable
for.
