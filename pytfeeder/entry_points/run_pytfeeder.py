import argparse
import asyncio

from pytfeeder.config import Config
import pytfeeder.dirs as dirs
from pytfeeder import init_feeder


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="package: %s" % __package__)
    parser.add_argument(
        "-c",
        "--config-file",
        default=dirs.default_config_path(),
        metavar="PATH",
        help="Location of config file (default: %(default)s)",
    )
    parser.add_argument(
        "--clean-cache",
        action="store_true",
        help="Deletes inactive channels and watched entries",
    )
    parser.add_argument(
        "-s", "--sync", action="store_true", help="Just update feeds and exit"
    )
    parser.add_argument(
        "-u", "--unviewed", action="store_true", help="Prints unviewed entries count"
    )

    return parser.parse_args()


def run():
    args = parse_args()
    config = Config(args.config_file)
    if not config:
        exit(1)

    feeder = init_feeder(config)
    if args.clean_cache:
        feeder.clean_cache()
    if args.sync:
        asyncio.run(feeder.sync_entries())
    if args.unviewed:
        print(feeder.unviewed_count())
