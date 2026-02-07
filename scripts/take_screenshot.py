import argparse
import os
from playwright.sync_api import sync_playwright


def parse_args():
    parser = argparse.ArgumentParser(
        description="Take a screenshot of a URL using Playwright."
    )
    parser.add_argument("--url", required=True, help="Page URL to capture.")
    parser.add_argument(
        "--out",
        required=True,
        help="Output image path (e.g. /tmp/screenshot.png).",
    )
    parser.add_argument("--width", type=int, default=1280)
    parser.add_argument("--height", type=int, default=720)
    parser.add_argument(
        "--full-page",
        action="store_true",
        help="Capture the full scrollable page.",
    )
    parser.add_argument(
        "--wait-ms",
        type=int,
        default=0,
        help="Extra wait time in milliseconds before capture.",
    )
    parser.add_argument(
        "--selector",
        default="",
        help="Optional CSS selector to wait for before capture.",
    )
    parser.add_argument(
        "--device-scale-factor",
        type=float,
        default=1.0,
        help="Device scale factor for the viewport.",
    )
    return parser.parse_args()


def ensure_dir(path):
    directory = os.path.dirname(os.path.abspath(path))
    if directory and not os.path.exists(directory):
        os.makedirs(directory, exist_ok=True)


def main():
    args = parse_args()
    ensure_dir(args.out)

    with sync_playwright() as p:
        browser = p.chromium.launch()
        context = browser.new_context(
            viewport={"width": args.width, "height": args.height},
            device_scale_factor=args.device_scale_factor,
        )
        page = context.new_page()
        page.goto(args.url, wait_until="networkidle")

        if args.selector:
            page.wait_for_selector(args.selector)

        if args.wait_ms > 0:
            page.wait_for_timeout(args.wait_ms)

        page.screenshot(path=args.out, full_page=args.full_page)
        context.close()
        browser.close()


if __name__ == "__main__":
    main()
