# mu2edaq-commandline-tools

Command line utilities for operating and diagnosing the Mu2e DAQ suite.

This is the home for the small, sharp CLI tools that do not warrant a repo of
their own: things you run from a shell on a DAQ node to inspect state, poke a
service, or answer "what does this machine think its configuration is?". They
share one dispatcher (`mu2edaq-tools`), one config file, and one precedence
rule, so a tool added here inherits all of it instead of reinventing it.

It ships both a Python package and a C++ library, and both resolve the config
file the same way — so a Python tool and a C++ tool started from the same
directory always agree about their settings.

Part of the [mu2edaq-main](https://github.com/Mu2e/mu2edaq-main) suite, where it
lives as a submodule.

## Installing and running

```bash
./bootstrap.sh --dev --cpp     # venv + editable install, plus the CMake build
source venv/bin/activate
mu2edaq-tools list             # what tools this build provides
mu2edaq-tools config           # the effective configuration and where it came from
```

`bootstrap.sh` is also the update command — re-run it any time to refresh
dependencies. Drop `--cpp` if you only want the Python side, and `--dev` if you
do not need pytest.

Without activating the venv:

```bash
./start-mu2edaq-commandline-tools.sh config --json
./stop-mu2edaq-commandline-tools.sh
```

`start-…` bootstraps on first run, refreshes dependencies on later runs, and
passes everything after its own options straight through to `mu2edaq-tools`.
Use `--no-update` on nodes with no network access. `stop-…` terminates whatever
`start-…` left running and cleans up the pidfile, `__pycache__`, and logs.

Requirements: Python 3.9+, PyYAML, and Requests for the Python side; CMake
3.16+ and a C++17 compiler for the C++ side. CppUnit is optional — see
[Testing](#testing). The supported targets are AlmaLinux and macOS.

## Configuration

Everything is config-driven. Four sources, highest precedence first:

```
command line  >  environment (MU2EDAQ_TOOLS_*)  >  YAML config file  >  defaults
```

None of them are required: with no config file and an empty environment the
defaults are a usable configuration.

The config file is searched for in this order, first hit wins:

| Order | Path |
|---|---|
| 1 | `$MU2EDAQ_TOOLS_CONFIG` |
| 2 | `./mu2edaq-commandline-tools.yaml` |
| 3 | `./config/mu2edaq-commandline-tools.yaml` |
| 4 | `<checkout>/config/mu2edaq-commandline-tools.yaml` (Python only) |
| 5 | `~/.config/mu2edaq/commandline-tools.yaml` |
| 6 | `/etc/mu2edaq/commandline-tools.yaml` |

`mu2edaq-tools config` prints which one is in use; `mu2edaq-tools-info --paths`
does the same for the C++ side, marking every candidate it considered.

### Schema

`config/mu2edaq-commandline-tools.yaml` is the annotated reference copy:

```yaml
# Cluster the tools act on by default.
cluster: mu2edaq

# Seconds to wait for mu2edaq-discovery responses before giving up.
discovery_timeout: 2.0

# Logging verbosity: DEBUG, INFO, WARNING, ERROR or CRITICAL.
log_level: INFO

# Directory for log files, relative to the working directory unless absolute.
log_dir: logs

# Colored terminal output.
color: true

otsdaq:
  default_instance: crv
  timeout: 10.0
  verify_tls: false
  ca_bundle: null
  instances:
    crv:
      gateway_url: https://localhost:3075
      # Optional; otherwise gateway port + 1 and host port 3047 are used.
      slow_controls_url: https://localhost:3076
      tfm_url: https://localhost:3047
      # Optional path only; the file must be chmod 600.
      cookie_file: ~/.config/mu2edaq/crv-cookie
```

The original top-level keys map 1:1 onto an environment variable
`MU2EDAQ_TOOLS_<KEY>` and a command line option `--<key-with-dashes>`:

| Key | Environment | Option | Default |
|---|---|---|---|
| `cluster` | `MU2EDAQ_TOOLS_CLUSTER` | `--cluster` | `mu2edaq` |
| `discovery_timeout` | `MU2EDAQ_TOOLS_DISCOVERY_TIMEOUT` | `--discovery-timeout` | `2.0` |
| `log_level` | `MU2EDAQ_TOOLS_LOG_LEVEL` | `--log-level` | `INFO` |
| `log_dir` | `MU2EDAQ_TOOLS_LOG_DIR` | `--log-dir` | `logs` |
| `color` | `MU2EDAQ_TOOLS_COLOR` | `--color` / `--no-color` | `true` |

The otsdaq settings use the same precedence. Environment overrides are named
`MU2EDAQ_TOOLS_OTSDAQ_INSTANCE`, `_GATEWAY_URL`, `_SLOW_CONTROLS_URL`,
`_TFM_URL`, `_TIMEOUT`, `_VERIFY_TLS`, `_CA_BUNDLE`, and `_COOKIE_FILE`.
`MU2EDAQ_TOOLS_OTSDAQ_COOKIE` supplies a Configuration Supervisor credential
without putting it in YAML or command history. It is not sent to the Gateway,
Slow Controls, or TFM origins.

Unknown keys in the YAML file are ignored rather than fatal, so a newer config
file does not break an older tool.

## Architecture

```
src/mu2edaq_commandline_tools/
    cli.py      dispatcher: argparse wiring + the COMMANDS registry
    config.py   the four-source precedence resolution, no I/O beyond the file
src/include/mu2edaq_cli_core.hpp   C++ API (config lookup + env overrides)
src/cpp/mu2edaq_cli_core.cpp       its implementation
src/cpp/mu2edaq_tools_info.cpp     mu2edaq-tools-info, the C++ diagnostic
```

Everything is synchronous and single-threaded; these are short-lived processes,
not services. `config.load()` is the only thing that touches the environment or
the filesystem, which is what makes the precedence testable.

The C++ version string is parsed out of the Python package's `__version__` at
CMake configure time, so the two cannot drift.

### Adding a tool

Register a `Command` in `cli.COMMANDS` — a help string, an optional hook that
adds argparse options, and a run hook that takes `(args, cfg)` and returns an
exit status:

```python
from mu2edaq_commandline_tools.cli import COMMANDS, Command

def _add_ping(parser):
    parser.add_argument("host")

def cmd_ping(args, cfg):
    print("pinging %s on %s" % (args.host, cfg["cluster"]))
    return 0

COMMANDS["ping"] = Command("check a node responds", _add_ping, cmd_ping)
```

It then shows up in `mu2edaq-tools list` and inherits the global options and
config resolution with no changes to the dispatcher.

## Testing

```bash
./bootstrap.sh --dev
source venv/bin/activate
pytest                              # Python: config precedence + CLI smokes

cmake -S . -B build && cmake --build build
ctest --test-dir build --output-on-failure   # C++
```

The C++ suite uses CppUnit when it is installed and falls back to an
`assert()`-based driver when it is not, so `ctest` covers the library either
way — it is never silently skipped.

## Reading a running otsdaq instance

Phase 1 provides modeled, read-only access to run-control state, run info,
artdaq state/reporting, live FE-macro inventory, Slow Controls PVs and alarms,
and console/system messages:

For installation, configuration, safe live smoke tests, automated testing, and
troubleshooting, see the
[Phase 1 otsdaq HOWTO](doc/otsdaq-phase1-howto.md).
The same material is available as a guided static website beginning at
[`html/index.html`](html/index.html).

```bash
mu2edaq-tools otsdaq state
mu2edaq-tools otsdaq daq-state --json
mu2edaq-tools otsdaq pv-read Mu2e:TDAQ_crv:daq08DTC:Temperature
mu2edaq-tools otsdaq console --watch --interval 1
mu2edaq-tools otsdaq state --watch --count 10 --json   # NDJSON
```

Every read command accepts `--instance`; URL, timeout, TLS, and CA overrides;
human output by default; and `--json`. Watch mode runs until Ctrl-C unless
bounded by `--count`.

TLS certificate verification is disabled by default and produces a warning on
stderr. Set `verify_tls: true`, pass `--verify-tls`, or configure a CA bundle to
enable it.

`mu2edaq-tools otsdaq raw` exposes arbitrary LID, RequestType, query, form, and
state-machine-handler calls. It is intentionally unrestricted, warns on every
invocation, and **can modify or interrupt a live DAQ system**. It emits
normalized JSON by default and exact XML with `--xml`.

[`doc/otsdaq-command-surface.md`](doc/otsdaq-command-surface.md) documents the
survey that defined this phase. The live `getFEMacroList` response is the
runtime source of truth because configured ROCs add forwarding macros.

`data/otsdaq-femacros.json` is the extracted macro inventory backing that
document, regenerated by `tools/extract-femacros.py` (see
`man ./man/man1/extract-femacros.py.1`). It is a source snapshot, not a live command
table — the DTC front end re-registers its ROCs' macros at configure time, so a
running system exposes more than the file lists.

## Documentation

Man pages, installed by `cmake --install` or readable in place:

```bash
man ./man/man1/mu2edaq-tools.1                      # the dispatcher
man ./man/man1/mu2edaq-otsdaq.1                     # otsdaq reads and raw API
man ./man/man1/mu2edaq-tools-info.1                 # the C++ diagnostic
man ./man/man1/bootstrap.sh.1
man ./man/man1/start-mu2edaq-commandline-tools.sh.1
man ./man/man1/stop-mu2edaq-commandline-tools.sh.1
man ./man/man1/extract-femacros.py.1                # otsdaq inventory extractor
man ./man/man3/mu2edaq_commandline_tools.3          # Python API
man ./man/man3/mu2edaq_cli_core.3                   # C++ API
```

Design and survey notes live in [`doc/`](doc/).
The operator/developer guide is
[`doc/otsdaq-phase1-howto.md`](doc/otsdaq-phase1-howto.md).

## License

MIT — see [LICENSE](LICENSE).
