from __future__ import annotations

import argparse
from pathlib import Path

import requests

from crossfit_wods.scraper import select_best_text_source


def load_html(url: str | None, html_file: str | None, timeout: int) -> tuple[str, str]:
    if url:
        response = requests.get(url, timeout=timeout)
        response.raise_for_status()
        return response.text, f"url:{url}"
    if html_file:
        path = Path(html_file)
        return path.read_text(encoding="utf-8"), f"file:{path}"
    raise ValueError("Provide --url or --html-file")


def main() -> None:
    parser = argparse.ArgumentParser(description="Debug extraction on recent CrossFit pages")
    parser.add_argument("--url", help="Remote page URL")
    parser.add_argument("--html-file", help="Local HTML file path")
    parser.add_argument("--timeout", type=int, default=20)
    parser.add_argument("--show-rejections", type=int, default=8)
    args = parser.parse_args()

    html, source = load_html(args.url, args.html_file, args.timeout)
    result = select_best_text_source(html)

    print(f"Source input: {source}")
    print(f"Extraction source: {result['source_type']}")
    print(f"Selector/Path: {result['locator']}")
    print(f"Score: {result['score']}")
    print(f"Rationale: {result['rationale']}")
    print(f"Why selected: {result['why_selected']}")
    print(f"Teaser-like: {result['teaser_like']}")
    print(f"Preview: {result['preview']}")

    rejected = result.get("rejected", [])
    print(f"\nRejected candidates (showing up to {args.show_rejections}):")
    for item in rejected[: args.show_rejections]:
        print(f"- [{item.get('source')}] {item.get('locator')} score={item.get('score')} reason={item.get('reason')}")

    richer_rejected = result.get("richer_rejected", [])
    print(f"\nTop richer rejected candidates ({len(richer_rejected)}):")
    for item in richer_rejected:
        print(
            f"- [{item.get('source')}] {item.get('locator')} score={item.get('score')} "
            f"length={item.get('length')} teaser_like={item.get('teaser_like')}"
        )


if __name__ == "__main__":
    main()
