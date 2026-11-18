import argparse
from pathlib import Path
import os

from alembic import command
from alembic.config import Config
from waitress import serve

from backend.app import make_app
from backend.demo import seed_demo

if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("action", choices=["upgrade", "seed-demo", "serve"])
    parser.add_argument("--port", type=int, default=8876)
    args = parser.parse_args()
    app = make_app(
        os.environ.get("LIMS_INSTANCE", Path(__file__).parent / "instance"),
        os.environ.get("LIMS_DATABASE_URL"),
    )
    engine = app.extensions["engine"]
    if args.action == "upgrade":
        config = Config()
        config.set_main_option("script_location", str(Path(__file__).parent / "backend" / "migrations"))
        config.attributes["engine"] = engine
        command.upgrade(config, "head")
    if args.action == "seed-demo":
        print("Demo created." if seed_demo(engine) else "Existing accounts preserved.")
    if args.action == "serve":
        print(f"http://127.0.0.1:{args.port}", flush=True)
        serve(app, host="127.0.0.1", port=args.port)
