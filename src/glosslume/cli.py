"""glosslume serve | glosslume dict import <ecdict.csv>"""
from __future__ import annotations

import argparse
import signal
import sys
import webbrowser
from pathlib import Path

from . import __version__


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(prog="glosslume", description="Read in the original language; click a word to see what it means here.")
    ap.add_argument("--version", action="version", version=__version__)
    sub = ap.add_subparsers(dest="cmd")
    sv = sub.add_parser("serve", help="start the reader at http://127.0.0.1:8780")
    sv.add_argument("--port", type=int, default=8780)
    sv.add_argument("--open", action="store_true", help="open the browser")
    sv.add_argument("--data", help="data directory (default: ~/Library/Application Support/Glosslume)")
    dc = sub.add_parser("dict", help="offline dictionary")
    dc.add_argument("action", choices=["import"])
    dc.add_argument("csv", type=Path)
    dc.add_argument("--data")
    args = ap.parse_args(argv)

    from .server.app import App, make_server
    if args.cmd == "dict":
        app = App(Path(args.data) if args.data else None)
        n = app.dictionary.import_csv(args.csv)
        print(f"imported {n} entries into {app.dictionary.path}")
        return 0
    if args.cmd in (None, "serve"):
        port = getattr(args, "port", 8780)
        app = App(Path(args.data) if getattr(args, "data", None) else None)
        app.local.autostart()                                      # the built-in model, if one has been downloaded
        srv = make_server(app, port)
        url = f"http://127.0.0.1:{port}"
        print(f"Glosslume {__version__} at {url}   (data: {app.data})")
        if getattr(args, "open", False):
            webbrowser.open(url)
        for sig in (signal.SIGTERM, getattr(signal, "SIGHUP", None)):       # closing the Terminal window: still stop the model server
            if sig is not None:
                signal.signal(sig, lambda *_: sys.exit(0))
        try:
            srv.serve_forever()
        except KeyboardInterrupt:
            print()
        finally:
            app.local.stop()                                       # do not leave the model server running
        return 0
    return 1


if __name__ == "__main__":
    sys.exit(main())
