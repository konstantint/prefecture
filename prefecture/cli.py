"""CLI for Prefecture."""

import pathlib
import sys

import dotenv

from prefecture import flows


def main():
    """Main entry point for the CLI."""
    # Load .env from current working directory only
    dotenv.load_dotenv(dotenv_path=pathlib.Path(".env"), override=True)

    if len(sys.argv) < 2:
        print("Usage: prefecture <path_to_config.yaml>")
        sys.exit(1)

    config_file = sys.argv[1]
    flows.run_flow(config_file=config_file)

if __name__ == "__main__":
    main()
