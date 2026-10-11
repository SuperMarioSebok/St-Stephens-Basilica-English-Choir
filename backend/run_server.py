"""Start the API (and the built frontend) on http://127.0.0.1:8000.

Access logging is OFF on purpose: request logs would record when someone sent feedback.
"""
import argparse

import uvicorn

from bvc import config

if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--data-dir")
    ap.add_argument("--host", default="127.0.0.1")
    ap.add_argument("--port", type=int, default=8000)
    args = ap.parse_args()
    if args.data_dir:
        config.set_data_dir(args.data_dir)
    uvicorn.run("bvc.app:app", host=args.host, port=args.port, access_log=False, proxy_headers=False)
