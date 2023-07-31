import argparse
import asyncio

from pytfeeder.config import Config
import pytfeeder.dirs as dirs
from pytfeeder import init_feeder


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
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
        "-p", "--print-config", action="store_true", help="prints config"
    )
    parser.add_argument(
        "-s",
        "--sync",
        action="store_true",
        help="Updates all feeds and prints new entries count",
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
    if args.print_config:
        print(config)
        exit(0)

    feeder = init_feeder(config)
    if args.clean_cache:
        feeder.clean_cache()
    if args.sync:
        before_updates = feeder.unviewed_count()
        asyncio.run(feeder.sync_entries())
        print(feeder.unviewed_count() - before_updates)
    if args.unviewed:
        print(feeder.unviewed_count())
