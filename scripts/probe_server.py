#!/usr/bin/env python3
"""Fixed diagnostic HTTP payload; use USB reverse for smoke, LAN for Wi-Fi policy."""
import argparse
import datetime
import http.server
import ipaddress
import json
import os
import pathlib
import urllib.parse


def main():
    os.umask(0o077)
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--bind", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=8023)
    parser.add_argument("--allowed-peer",type=ipaddress.ip_address)
    parser.add_argument("--log", type=pathlib.Path, default=pathlib.Path("diagnostics/probe-server.jsonl"))
    args = parser.parse_args()
    args.log.parent.mkdir(parents=True, exist_ok=True)
    payload = os.urandom(256 * 1024)

    class Handler(http.server.BaseHTTPRequestHandler):
        def do_GET(self):
            if args.allowed_peer and self.client_address[0]!=str(args.allowed_peer):
                self.send_error(403);return
            url = urllib.parse.urlsplit(self.path)
            if url.path != "/payload":
                self.send_error(404); return
            query = urllib.parse.parse_qs(url.query)
            entry = {"utc": datetime.datetime.now(datetime.timezone.utc).isoformat(),
                     "peer": self.client_address[0], "bytes": len(payload),
                     "probe": {key: query.get(key, [""])[0][:100] for key in ("uid", "package", "probe")}}
            self.send_response(200)
            self.send_header("Content-Type", "application/octet-stream")
            self.send_header("Content-Length", str(len(payload)))
            self.send_header("Cache-Control", "no-store")
            self.end_headers()
            try:
                self.wfile.write(payload)
                entry["write_completed"] = True
            except (BrokenPipeError, ConnectionResetError):
                entry["write_completed"] = False
            with args.log.open("a") as output:
                output.write(json.dumps(entry) + "\n")
        def log_message(self, format, *args):
            pass

    print(f"Serving diagnostic payload on {args.bind}:{args.port}; requests logged at {args.log}", flush=True)
    http.server.ThreadingHTTPServer((args.bind, args.port), Handler).serve_forever()


if __name__ == "__main__":
    main()
