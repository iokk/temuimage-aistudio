#!/usr/bin/env python3
"""Run controlled GPT Image edit probes against the active provider."""

import argparse
import copy
import json
import time
import types
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path
import sys

from PIL import Image

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

import app  # noqa: E402


def parse_args(argv=None):
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--allow-paid-requests",
        action="store_true",
        help="Acknowledge that this diagnostic issues paid image requests.",
    )
    parser.add_argument("--image", required=True)
    parser.add_argument("--provider-id", default="")
    parser.add_argument("--model", default="")
    parser.add_argument("--concurrency", type=int, default=1)
    parser.add_argument("--requests", type=int, default=1)
    parser.add_argument("--max-dimension", type=int, default=2048)
    parser.add_argument("--retries", type=int, default=1)
    parser.add_argument("--quality", choices=("low", "medium", "high"), default="medium")
    parser.add_argument("--inter-request-delay", type=float, default=0)
    parser.add_argument("--output-dir", default="/tmp/tulite-image-probes")
    args = parser.parse_args(argv)
    if not args.allow_paid_requests:
        parser.error("--allow-paid-requests is required for paid image probes")
    if not 1 <= args.requests <= 5:
        parser.error("--requests must be between 1 and 5")
    if not 1 <= args.concurrency <= 2:
        parser.error("--concurrency must be between 1 and 2")
    if not 0 <= args.retries <= 1:
        parser.error("--retries must be between 0 and 1")
    return args


def resolve_probe_provider(args):
    provider = (
        app.get_provider_by_id(args.provider_id)
        if args.provider_id
        else app.get_active_provider()
    )
    if not provider or not provider.get("api_key"):
        raise SystemExit("No selected provider with an API key")
    provider = copy.deepcopy(provider)
    if args.model:
        provider["image_model"] = args.model
    if not provider.get("image_model"):
        raise SystemExit("The selected provider has no image model")
    return provider


def build_start_event(provider, source_size, args):
    return {
        "event": "start",
        "model": provider.get("image_model"),
        "source_size": source_size,
        "concurrency": args.concurrency,
        "requests": args.requests,
        "retries": args.retries,
        "quality": args.quality,
        "inter_request_delay": args.inter_request_delay,
    }


def main():
    args = parse_args()
    provider = resolve_probe_provider(args)

    source = Image.open(args.image).convert("RGB")
    if max(source.size) > args.max_dimension:
        source.thumbnail((args.max_dimension, args.max_dimension), Image.Resampling.LANCZOS)

    output_dir = Path(args.output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    prompt = (
        "Keep the same product identity and create a clean studio product "
        "photograph on a white background."
    )

    print(json.dumps(build_start_event(provider, source.size, args)), flush=True)

    def probe(index):
        if index > 1 and args.inter_request_delay > 0:
            time.sleep(args.inter_request_delay)
        client = app.create_ai_client(provider, model=provider.get("image_model"))
        original_call = client._openai_call

        def controlled_call(self, path, payload=None, multipart=None, timeout_seconds=120, retries=3):
            return original_call(
                path,
                payload=payload,
                multipart=multipart,
                timeout_seconds=timeout_seconds,
                retries=args.retries,
            )

        client._openai_call = types.MethodType(controlled_call, client)
        started = time.monotonic()
        try:
            data = client._images_edits(
                prompt,
                [source.copy()],
                "1024x1024",
                args.quality,
            )
            image = client._extract_openai_image(data)
            if image is None:
                raise RuntimeError("The response contained no decodable image")
            path = output_dir / f"probe-{int(time.time())}-{index}.png"
            image.save(path)
            return {
                "event": "result",
                "index": index,
                "ok": True,
                "elapsed_seconds": round(time.monotonic() - started, 1),
                "output": str(path),
                "output_size": image.size,
            }
        except Exception as error:
            return {
                "event": "result",
                "index": index,
                "ok": False,
                "elapsed_seconds": round(time.monotonic() - started, 1),
                "error": app.sanitize_task_error(str(error)),
            }

    results = []
    with ThreadPoolExecutor(max_workers=max(1, args.concurrency)) as executor:
        futures = [executor.submit(probe, index + 1) for index in range(args.requests)]
        for future in as_completed(futures):
            result = future.result()
            results.append(result)
            print(json.dumps(result, ensure_ascii=False), flush=True)

    successes = sum(1 for result in results if result["ok"])
    summary = {
        "event": "summary",
        "successes": successes,
        "failures": len(results) - successes,
        "total": len(results),
    }
    print(json.dumps(summary), flush=True)
    raise SystemExit(0 if successes == len(results) else 1)


if __name__ == "__main__":
    main()
