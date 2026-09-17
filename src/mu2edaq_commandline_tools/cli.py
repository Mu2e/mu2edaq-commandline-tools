"""`mu2edaq-tools` - dispatcher for the Mu2e DAQ command line utilities.

Each utility is a subcommand registered in COMMANDS below. A subcommand is a
(help text, add-arguments hook, run hook) triple; the run hook is called with
the parsed arguments and the effective configuration.

Adding a tool:

    def _add_foo(p):        # optional, declare argparse options
        p.add_argument("--bar")

    def cmd_foo(args, cfg): # return a process exit status
        ...
        return 0

    COMMANDS["foo"] = Command("what foo does", _add_foo, cmd_foo)
"""

from __future__ import annotations

import argparse
import json
import sys
from collections import namedtuple
from typing import Any, Dict

from . import __version__
from . import config as configmod
from .otsdaq import commands as otsdaq_commands

Command = namedtuple("Command", "help add_arguments run")

PROG = "mu2edaq-tools"


# ----------------------------------------------------------------- commands --


def cmd_list(args: argparse.Namespace, cfg: Dict[str, Any]) -> int:
    """Print the registered tools."""
    width = max(len(name) for name in COMMANDS)
    for name in sorted(COMMANDS):
        print("  %-*s  %s" % (width, name, COMMANDS[name].help))
    return 0


def _add_config(parser: argparse.ArgumentParser) -> None:
    parser.add_argument(
        "--json", action="store_true", help="emit the configuration as JSON"
    )


def cmd_config(args: argparse.Namespace, cfg: Dict[str, Any]) -> int:
    """Show the effective configuration and where it came from."""
    source = cfg.get("_config_file")
    values = {k: v for k, v in cfg.items() if not k.startswith("_")}
    if args.json:
        print(json.dumps({"config_file": source, "values": values}, indent=2, sort_keys=True))
        return 0
    print("config file: %s" % (source or "(none found, using defaults)"))
    width = max(len(k) for k in values)
    for key in sorted(values):
        print("  %-*s  %s" % (width, key, values[key]))
    return 0


def cmd_version(args: argparse.Namespace, cfg: Dict[str, Any]) -> int:
    """Print the package version."""
    print("%s %s" % (PROG, __version__))
    return 0


COMMANDS: Dict[str, Command] = {
    "list": Command("list the available tools", None, cmd_list),
    "config": Command("show the effective configuration", _add_config, cmd_config),
    "version": Command("show the package version", None, cmd_version),
    "otsdaq": Command(
        "read status and diagnostics from otsdaq",
        otsdaq_commands.add_arguments,
        otsdaq_commands.run,
    ),
}


# -------------------------------------------------------------------- parser --


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog=PROG,
        description="Command line utilities for the Mu2e DAQ suite.",
        epilog="Options override the environment (MU2EDAQ_TOOLS_*), which "
        "overrides the YAML config file, which overrides the defaults.",
    )
    parser.add_argument("-V", "--version", action="version",
                        version="%s %s" % (PROG, __version__))
    parser.add_argument("-c", "--config", metavar="FILE",
                        help="path to the YAML config file")
    parser.add_argument("--cluster", metavar="NAME",
                        help="cluster to operate on (default: %s)"
                             % configmod.DEFAULTS["cluster"])
    parser.add_argument("--discovery-timeout", type=float, metavar="SECONDS",
                        help="seconds to wait for discovery responses "
                             "(default: %s)" % configmod.DEFAULTS["discovery_timeout"])
    parser.add_argument("--log-level", metavar="LEVEL",
                        choices=["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"],
                        help="logging verbosity (default: %s)"
                             % configmod.DEFAULTS["log_level"])
    parser.add_argument("--log-dir", metavar="DIR",
                        help="directory for log files (default: %s)"
                             % configmod.DEFAULTS["log_dir"])
    color = parser.add_mutually_exclusive_group()
    color.add_argument("--color", dest="color", action="store_true", default=None,
                       help="force colored output")
    color.add_argument("--no-color", dest="color", action="store_false", default=None,
                       help="disable colored output")

    subs = parser.add_subparsers(dest="command", metavar="<command>")
    for name in sorted(COMMANDS):
        cmd = COMMANDS[name]
        sub = subs.add_parser(name, help=cmd.help, description=cmd.help)
        if cmd.add_arguments is not None:
            cmd.add_arguments(sub)
    return parser


def main(argv=None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)

    if not args.command:
        parser.print_help()
        return 2

    overrides = {
        "cluster": args.cluster,
        "discovery_timeout": args.discovery_timeout,
        "log_level": args.log_level,
        "log_dir": args.log_dir,
        "color": args.color,
    }
    try:
        cfg = configmod.load(args.config, overrides)
    except (OSError, ValueError, RuntimeError) as exc:
        print("%s: %s" % (PROG, exc), file=sys.stderr)
        return 1

    return COMMANDS[args.command].run(args, cfg)


if __name__ == "__main__":
    sys.exit(main())
