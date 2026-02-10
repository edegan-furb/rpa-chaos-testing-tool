# RPA Chaos Testing Tool

RPA Chaos is a lightweight Python CLI for running Playwright-based RPA bots under
repeatable chaos conditions. It wraps Playwright pages with hooks that can inject
random delays, modal overlays, and network throttling/offline bursts so you can
stress-test automation flows.

## Features

- **Deterministic chaos** via a seed per run.
- **Multiple chaos experiments** (delay, modal overlay, network throttling).
- **CLI reporting** with pass/fail and timing summary.
- **Works with any sync Playwright bot** exposed as `module:function`.

## Requirements

- Python 3.10+
- Playwright (and installed browsers)

Install dependencies and browsers:

```bash
python -m venv .venv
source .venv/bin/activate
pip install -e .
playwright install
```

## Usage

Run a bot multiple times with chaos enabled:

```bash
rpa-chaos examples.demo_bot:run --runs 5 --headless
```

Disable chaos for a clean baseline:

```bash
rpa-chaos examples.demo_bot:run --runs 3 --no-chaos
```

Open a URL before your bot runs (useful when your bot expects a starting page):

```bash
rpa-chaos examples.demo_bot:run --base-url https://example.com
```

## Writing a Bot

A bot is any callable that accepts a Playwright `page`. For example:

```python
# examples/demo_bot.py

def run(page):
    page.goto("https://example.com")
    page.get_by_role("link", name="Learn more").click()
```

Run it via:

```bash
rpa-chaos run examples.demo_bot:run
```

## Chaos Experiments

The default experiments are configured in `chaos/runner.py`:

- `RandomDelay`: adds a small delay before actions.
- `ModalOverlay`: injects an overlay that blocks interaction temporarily.
- `NetworkChaos`: throttles or briefly disables the network.

You can adjust the experiment list, probabilities, and timing values in
`chaos/runner.py` to match your needs.

## Development

Run the CLI directly with Python:

```bash
python -m chaos.runner run examples.demo_bot:run
```
