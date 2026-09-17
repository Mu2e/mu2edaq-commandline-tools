"""argparse wiring and presentation for ``mu2edaq-tools otsdaq``."""

from __future__ import annotations

import argparse
import json
import sys
import time
from datetime import datetime, timezone
from typing import Any, Callable, Dict, Iterable, List, Mapping, Optional, Tuple

from .client import (
    LID_CONFIG,
    LID_CONSOLE,
    LID_GATEWAY,
    LID_MACRO_MAKER,
    LID_SLOW_CONTROLS,
    LID_TFM,
    OtsdaqClient,
)
from .models import FEMacro, OtsdaqError
from .settings import resolve_instance

SERVICE_LIDS = {
    "gateway": LID_GATEWAY,
    "console": LID_CONSOLE,
    "config": LID_CONFIG,
    "slow-controls": LID_SLOW_CONTROLS,
    "tfm": LID_TFM,
    "macro": LID_MACRO_MAKER,
}


def add_arguments(parser: argparse.ArgumentParser) -> None:
    """Add the complete nested otsdaq command tree."""
    subcommands = parser.add_subparsers(dest="otsdaq_command", metavar="<read>")

    state = subcommands.add_parser("state", help="show the current run-control state")
    _add_typed_options(state)

    run_info = subcommands.add_parser("run-info", help="show current or historical run info")
    run_info.add_argument("run_number", nargs="?", type=int, default=0)
    _add_typed_options(run_info)

    daq_report = subcommands.add_parser("daq-report", help="show the artdaq DAQ report")
    _add_typed_options(daq_report)

    daq_state = subcommands.add_parser("daq-state", help="show the artdaq DAQ state")
    _add_typed_options(daq_state)

    macros = subcommands.add_parser("macros", help="list live FE and stored macros")
    _add_typed_options(macros)

    pv_list = subcommands.add_parser("pv-list", help="list Slow Controls PVs")
    _add_typed_options(pv_list)

    pv_read = subcommands.add_parser("pv-read", help="read Slow Controls PV values")
    pv_read.add_argument("pv", nargs="+", metavar="PV")
    _add_typed_options(pv_read)

    pv_settings = subcommands.add_parser("pv-settings", help="read Slow Controls PV settings")
    pv_settings.add_argument("pv", nargs="+", metavar="PV")
    _add_typed_options(pv_settings)

    alarms = subcommands.add_parser("alarms", help="read Slow Controls alarms")
    alarms.add_argument("pv", nargs="*", metavar="PV")
    _add_typed_options(alarms)

    alarm_checks = subcommands.add_parser(
        "alarm-checks", help="read Slow Controls alarm-check status"
    )
    _add_typed_options(alarm_checks)

    console = subcommands.add_parser("console", help="read otsdaq console messages")
    console.add_argument("--lcount", type=int, default=0, metavar="N")
    _add_typed_options(console)

    messages = subcommands.add_parser("messages", help="read gateway system messages")
    messages.add_argument("--history", action="store_true")
    _add_typed_options(messages)

    raw = subcommands.add_parser("raw", help="send an expert raw xdaq request")
    raw.add_argument("request_type", metavar="REQUEST_TYPE")
    raw.add_argument("--service", choices=sorted(SERVICE_LIDS))
    raw.add_argument("--lid", type=int, metavar="LID")
    raw.add_argument(
        "--handler", choices=("request", "state-machine"), default="request"
    )
    raw.add_argument("--query", action="append", default=[], metavar="KEY=VALUE")
    raw.add_argument("--form", action="append", default=[], metavar="KEY=VALUE")
    raw.add_argument("--xml", action="store_true", help="emit exact XML instead of JSON")
    _add_connection_options(raw)


def _add_connection_options(parser: argparse.ArgumentParser) -> None:
    parser.add_argument("--instance", metavar="NAME", help="named otsdaq profile")
    parser.add_argument("--gateway-url", metavar="ORIGIN")
    parser.add_argument("--slow-controls-url", metavar="ORIGIN")
    parser.add_argument("--tfm-url", metavar="ORIGIN")
    parser.add_argument("--timeout", type=float, metavar="SECONDS")
    tls = parser.add_mutually_exclusive_group()
    tls.add_argument("--verify-tls", dest="verify_tls", action="store_true", default=None)
    tls.add_argument("--insecure", dest="verify_tls", action="store_false", default=None)
    parser.add_argument("--ca-bundle", metavar="FILE")


def _add_typed_options(parser: argparse.ArgumentParser) -> None:
    _add_connection_options(parser)
    parser.add_argument("--json", action="store_true", help="emit stable JSON")
    parser.add_argument("--watch", action="store_true", help="poll until interrupted")
    parser.add_argument("--interval", type=float, default=2.0, metavar="SECONDS")
    parser.add_argument("--count", type=int, metavar="N", help="stop after N watch samples")


def run(args: argparse.Namespace, cfg: Mapping[str, Any]) -> int:
    """Run the selected otsdaq operation."""
    if not args.otsdaq_command:
        print("mu2edaq-tools otsdaq: a read command is required", file=sys.stderr)
        return 2
    try:
        instance = resolve_instance(
            cfg,
            instance=args.instance,
            gateway_url=args.gateway_url,
            slow_controls_url=args.slow_controls_url,
            tfm_url=args.tfm_url,
            timeout=args.timeout,
            verify_tls=args.verify_tls,
            ca_bundle=args.ca_bundle,
        )
        if not instance.requests_verify:
            print(
                "warning: TLS certificate verification is disabled for otsdaq instance %s"
                % instance.name,
                file=sys.stderr,
            )
        client = OtsdaqClient(instance)
        if args.otsdaq_command == "raw":
            return _run_raw(args, client)
        return _run_typed(args, client)
    except OtsdaqError as exc:
        print("mu2edaq-tools otsdaq: %s" % exc, file=sys.stderr)
        return 1


def _run_typed(args: argparse.Namespace, client: OtsdaqClient) -> int:
    if args.interval <= 0:
        print("mu2edaq-tools otsdaq: --interval must be greater than zero", file=sys.stderr)
        return 2
    if args.count is not None and args.count <= 0:
        print("mu2edaq-tools otsdaq: --count must be greater than zero", file=sys.stderr)
        return 2
    if args.count is not None and not args.watch:
        print("mu2edaq-tools otsdaq: --count requires --watch", file=sys.stderr)
        return 2

    operation = _operation(args, client)
    samples = args.count if args.watch and args.count is not None else 1
    unbounded = args.watch and args.count is None
    index = 0
    try:
        while unbounded or index < samples:
            result = operation()
            envelope = {
                "instance": client.instance.name,
                "command": args.otsdaq_command,
                "timestamp": datetime.now(timezone.utc).isoformat(),
                "data": _jsonable(result),
            }
            if args.json:
                print(json.dumps(envelope, sort_keys=True))
            else:
                if args.watch:
                    print("[%s]" % envelope["timestamp"])
                _print_human(result)
                if args.watch and (unbounded or index + 1 < samples):
                    print()
            index += 1
            if args.watch and (unbounded or index < samples):
                time.sleep(args.interval)
    except KeyboardInterrupt:
        return 130
    return 0


def _operation(
    args: argparse.Namespace, client: OtsdaqClient
) -> Callable[[], Any]:
    command = args.otsdaq_command
    if command == "console":
        cursor = [args.lcount]

        def console() -> Dict[str, Any]:
            data = client.console_messages(cursor[0])
            advanced = False
            for key in ("lcount", "lastCount", "last_count", "count"):
                if key in data:
                    try:
                        cursor[0] = int(data[key])
                        advanced = True
                    except (TypeError, ValueError):
                        pass
                    break
            if not advanced:
                messages = data.get("message", data.get("messages", []))
                if messages:
                    cursor[0] += len(messages) if isinstance(messages, list) else 1
            return data

        return console
    operations: Dict[str, Callable[[], Any]] = {
        "state": client.current_state,
        "run-info": lambda: client.run_info(args.run_number),
        "daq-report": client.daq_report,
        "daq-state": client.daq_state,
        "macros": client.macro_list,
        "pv-list": client.pv_list,
        "pv-read": lambda: client.pv_data(args.pv),
        "pv-settings": lambda: client.pv_settings(args.pv),
        "alarms": lambda: client.alarms(args.pv),
        "alarm-checks": client.alarm_checks,
        "messages": lambda: client.system_messages(args.history),
    }
    return operations[command]


def _run_raw(args: argparse.Namespace, client: OtsdaqClient) -> int:
    print(
        "warning: raw otsdaq requests are unrestricted and may change a live DAQ system",
        file=sys.stderr,
    )
    try:
        query = _key_values(args.query)
        form = _key_values(args.form)
    except ValueError as exc:
        print("mu2edaq-tools otsdaq raw: %s" % exc, file=sys.stderr)
        return 2
    service = args.service
    lid = args.lid if args.lid is not None else SERVICE_LIDS[service or "gateway"]
    response = client.request(
        args.request_type,
        lid=lid,
        service=service,
        query=query,
        form=form,
        handler=args.handler,
        require_data=False,
    )
    if args.xml:
        sys.stdout.write(response.xml)
    else:
        print(json.dumps(response.to_dict(), indent=2, sort_keys=True))
    return 0


def _key_values(items: Iterable[str]) -> Dict[str, str]:
    result: Dict[str, str] = {}
    for item in items:
        if "=" not in item:
            raise ValueError("expected KEY=VALUE, got %r" % item)
        key, value = item.split("=", 1)
        if not key:
            raise ValueError("empty key in %r" % item)
        result[key] = value
    return result


def _jsonable(value: Any) -> Any:
    if isinstance(value, FEMacro):
        return value.to_dict()
    if isinstance(value, list):
        return [_jsonable(item) for item in value]
    if isinstance(value, dict):
        return {key: _jsonable(item) for key, item in value.items()}
    return value


def _print_human(value: Any) -> None:
    if isinstance(value, list) and (not value or isinstance(value[0], FEMacro)):
        macros: List[FEMacro] = value
        if not macros:
            print("(no macros found)")
            return
        headers = ("TYPE", "FE UID", "MACRO", "INPUTS", "OUTPUTS")
        rows: List[Tuple[str, str, str, str, str]] = [
            (
                macro.macro_type,
                macro.fe_uid or "-",
                macro.name,
                ", ".join(macro.inputs) or "-",
                ", ".join(macro.outputs) or "-",
            )
            for macro in macros
        ]
        widths = [
            max(len(headers[i]), max(len(row[i]) for row in rows)) for i in range(5)
        ]
        print("  ".join(headers[i].ljust(widths[i]) for i in range(5)))
        for row in rows:
            print("  ".join(row[i].ljust(widths[i]) for i in range(5)))
        return
    if isinstance(value, dict):
        if not value:
            print("(no data)")
            return
        width = max(len(str(key)) for key in value)
        for key in sorted(value):
            item = value[key]
            rendered = (
                json.dumps(item, sort_keys=True)
                if isinstance(item, (dict, list))
                else str(item)
            )
            print("  %-*s  %s" % (width, key, rendered))
        return
    if isinstance(value, list):
        if not value:
            print("(no data)")
        else:
            for item in value:
                print(json.dumps(item, sort_keys=True) if isinstance(item, (dict, list)) else item)
        return
    print(value)
