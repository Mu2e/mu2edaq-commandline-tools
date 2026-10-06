# mu2edaq-commandline-tools — interfaces

Reviewed 2026-10-06 against `21420c9` on branch `mu2e-sept-mega-review`.
Line references are to that tree. "Verified" means the behaviour was run in
this review (macOS, Python 3.12.1 and 3.9.6, Apple clang C++17, CppUnit 1.15.1);
everything else is read from source.

## 1. Command line

### 1.1 Dispatcher

```
mu2edaq-tools [-c FILE] [--cluster NAME] [--discovery-timeout S] [--log-level L]
              [--log-dir DIR] [--color|--no-color] {list,config,version,otsdaq} ...
mu2edaq-tools -V | -h
```

Global options must precede the subcommand (`cli.py:88-124`). `config --json`
prints `{"config_file": path|null, "values": {...}}` (`cli.py:53-64`). Exit
status: 0; 1 for an unreadable or non-mapping config file or missing PyYAML
(`cli.py:142-146`); 2 for no subcommand or an argparse error. A YAML syntax
error is not caught and exits 1 with a traceback (verified; CLT-011).

### 1.2 `otsdaq` subcommand

| Command | Arguments | RequestType | LID | Origin | Form fields |
|---|---|---|---|---|---|
| `state` | | `getCurrentState` | 200 | gateway | |
| `run-info` | `[RUN_NUMBER]` (default 0 = current) | `getRunInfo` | 200 | gateway | query `RunNumber` |
| `daq-report` | | `getDAQReport` | 302 | TFM | |
| `daq-state` | | `getDAQState` | 302 | TFM | |
| `macros` | | `getFEMacroList` | 800 | gateway | |
| `pv-list` | | `getList` | 282 | Slow Controls | |
| `pv-read` | `PV...` (1+) | `getPvData` | 282 | Slow Controls | `pvList=a,b,` |
| `pv-settings` | `PV...` (1+) | `getPVSettings` | 282 | Slow Controls | `pvList=a,b,` |
| `alarms` | `[PV...]` | `getLastAlarmsData` | 282 | Slow Controls | `pvList=` (`,` when no PV given) |
| `alarm-checks` | | `getAlarmsCheck` | 282 | Slow Controls | |
| `console` | `[--lcount N]` | `GetConsoleMsgs` | 260 | gateway | `lcount` |
| `messages` | `[--history]` | `getSystemMessages` | 200 | gateway | `history=true` |
| `raw` | `REQUEST_TYPE` | any | any | by `--service`, else by LID | any `--form`, `--query` |

Sources: `commands.py:34-92`, `client.py:188-288`.

Every typed command also takes the connection options `--instance`,
`--gateway-url`, `--slow-controls-url`, `--tfm-url`, `--timeout`,
`--verify-tls|--insecure`, `--ca-bundle` (`commands.py:95-104`) and the output
options `--json`, `--watch`, `--interval` (default 2), `--count`
(`commands.py:107-112`). `raw` takes the connection options plus `--service`,
`--lid`, `--handler {request,state-machine}`, repeatable `--query K=V` and
`--form K=V`, and `--xml` (`commands.py:82-92`).

Output: a human key/value or macro table by default; with `--json` one
`{"instance","command","timestamp","data"}` object per sample, NDJSON under
`--watch` (`commands.py:164-171`). `raw` prints the normalized XML as JSON, or
the exact response with `--xml` (`commands.py:249-252`).

Exit status (`commands.py:115-183`, `:227-253`): 0; 1 for any `OtsdaqError`
(config, transport, HTTP, XML, embedded JSON, server error); 2 for no read
command, non-positive `--interval`/`--count`, `--count` without `--watch`, or a
malformed `K=V`; 130 on Ctrl-C.

### 1.3 Other executables

| Executable | Options | Man page |
|---|---|---|
| `mu2edaq-tools-info` (C++) | `-c FILE`, `-p/--paths`, `-V`, `-h`; exit 0/2 | `man/man1/mu2edaq-tools-info.1` |
| `tools/extract-femacros.py` | `-r DIR`, `-o FILE\|-`, `-p GLOB`, `-q` | `man/man1/extract-femacros.py.1` |
| `bootstrap.sh` | `--dev`, `--cpp`, `--clean`, `--python PATH`, `--version` | `man/man1/bootstrap.sh.1` |
| `start-mu2edaq-commandline-tools.sh` | `--no-update` (first argument only), then passthrough | `man/man1/start-mu2edaq-commandline-tools.sh.1` |
| `stop-mu2edaq-commandline-tools.sh` | `--timeout SECS`, `--keep-logs` | `man/man1/stop-mu2edaq-commandline-tools.sh.1` |
| `html/validate.py` | none; run as `python3 html/validate.py` | waived (site test helper, `html/README.md`) |

## 2. Configuration resolution

### 2.1 Python

Highest first: command line, `MU2EDAQ_TOOLS_*`, one YAML file, `DEFAULTS`
(`config.py:1-21`, `:196-223`). Details that matter:

- An empty environment variable is unset (`config.py:180`, `:185`;
  `settings.py:167`).
- `-c FILE` makes `FILE` the only candidate; if it does not exist the defaults
  are used, silently (`config.py:122-124`, `:137-140`; verified).
- Unknown top-level keys are ignored (`config.py:155`).
- For `otsdaq`, the effective order is: code default < top-level `otsdaq` keys
  from file, then environment (`config.py:211-215`) < the selected profile
  (`settings.py:156`) < environment again (`settings.py:166-168`) < command-line
  options (`settings.py:169-179`). A CA bundle from any layer forces
  verification on, so `--insecure` loses to a file or environment
  `ca_bundle` (`settings.py:200-206`). This is the only inversion of the
  stated precedence, and it fails safe.
- There is no `.env` layer (CLT-013).

### 2.2 C++

`mu2edaq_cli_core` provides only the file search (`mu2edaq_cli_core.cpp:36-68`)
and single-variable lookup `env_override(key, fallback)` (`:70-78`), which
upper-cases `key`, maps `-` to `_`, and treats an empty value as unset. It has
no YAML parser, no defaults table and no command-line layer. A C++ tool that
wants the documented precedence must parse the file itself and pass the file
value as `fallback`.

### 2.3 Do Python and C++ resolve identically?

No. The header claims they do (`src/include/mu2edaq_cli_core.hpp:4-6`, "a C++
tool and a Python tool started from the same place read the same YAML file"),
as does `README.md:11-13`. The search lists differ in one entry and in `~`
handling:

| | Python | C++ |
|---|---|---|
| explicit path | `Path(explicit).expanduser()` (`config.py:123`) | literal (`mu2edaq_cli_core.cpp:38-40`) |
| `$MU2EDAQ_TOOLS_CONFIG` | `expanduser()` (`config.py:127`) | literal (`:43-44`) |
| package `config/` entry | yes (`config.py:130`) | absent |
| user entry | `Path.home()` | `$HOME`, Windows `USERPROFILE` (`:20-28`); omitted if empty |
| existence test | `Path.is_file()` (follows symlinks) | `fs::is_regular_file` (follows symlinks) |
| empty env var | unset | unset |

Cases run in this review, with `HOME` pointed at a scratch directory,
`cwd` a directory with no config, Python run from the checkout as the editable
install would, and `mu2edaq-tools-info` built from this tree:

| Case | Python reads | C++ reports | Same? |
|---|---|---|---|
| A. no cwd config; `~/.config/mu2edaq/commandline-tools.yaml` present | checkout `config/mu2edaq-commandline-tools.yaml` (`cluster: mu2edaq`) | `~/.config/mu2edaq/commandline-tools.yaml` | **no** |
| B. `MU2EDAQ_TOOLS_CONFIG='~/site.yaml'` (quoted, so the shell does not expand it) | `~/site.yaml` (`cluster: from-site-file`) | skips it; `~/.config/mu2edaq/commandline-tools.yaml` | **no** |
| C. `-c nope.yaml` (missing) | none, defaults | none, defaults | yes |
| D. `-c site.yaml`, `MU2EDAQ_TOOLS_CLUSTER=from-env`, `--cluster from-cli` | `from-cli` | n/a (no CLI layer) | — |
| E. same as D without `--cluster` | `from-env` | `env_override("cluster", …)` = `from-env` | yes |
| F. same as E with `MU2EDAQ_TOOLS_CLUSTER=` (empty) | `from-site-file` | fallback (caller's choice; library cannot read the file) | depends on caller |
| G. `.env` in cwd containing `MU2EDAQ_TOOLS_CLUSTER=from-dotenv` | ignored (`from-site-file`) | ignored | yes, both ignore it |

Case A is the common one: any directory without its own config file, with an
editable install. The C++ test suite (`tests/cpp/test_cli_core.cpp:24-55`) and
the Python tests check each side alone; nothing compares them (CLT-004).

## 3. otsdaq HTTP protocol (client side)

### 3.1 Origins and LIDs

| LID | Supervisor | Origin |
|---|---|---|
| 200 | Gateway | `gateway_url` |
| 260 | Console | `gateway_url` |
| 281 | Configuration | `gateway_url` |
| 800 | Macro Maker | `gateway_url` |
| 282 | Slow Controls | `slow_controls_url`, default gateway host, gateway port + 1 (`settings.py:67-74`) |
| 302 | TFM | `tfm_url`, default gateway host, port 3047 (`settings.py:183`) |

`origin_for()` (`settings.py:32-37`) routes by `--service` when given, else by
LID 282/302, else gateway. Origins must be `http` or `https`, with no path,
query, fragment or user info (`settings.py:40-55`). Plain `http` is accepted;
the TLS warning still prints in that case because it keys on the verify flag,
not the scheme.

**TFM collision (CLT-001).** Port 3047 is the CRV web client's constant
(`otsdaq-mu2e-crv/UserWebGUI/js/mu2e.js:9`). With the HOWTO's three-profile
example (`doc/otsdaq-phase1-howto.md:119-128`), verified:

```
crv     https://localhost:3075 https://localhost:3076 https://localhost:3047
tracker https://localhost:3175 https://localhost:3176 https://localhost:3047
calo    https://localhost:3275 https://localhost:3276 https://localhost:3047
```

The same holds on site, where the shifter docs place every subsystem's otsdaq
on `mu2e-cfo-01` at different gateway ports
(`mu2edaq-operations/shifter/docs/connecting.md:87-103`).

### 3.2 Request and response

```
POST <origin>/urn:xdaq-application:lid=<LID>/Request?RequestType=<name>[&<query>]
POST <origin>/urn:xdaq-application:lid=<LID>/StateMachineXgiHandler?StateMachine=<name>   (raw --handler state-machine)
Content-Type: application/x-www-form-urlencoded     body: form fields
```

`client.py:98-168`. A response is accepted only if the status is 2xx, the body
parses as XML, and the root is `<ROOT>`; typed reads also require
`<ROOT>/<DATA>`. It is rejected if any `Error` or `ERROR` element has a value or
text, if `DATA/state_transition_attempted` is `0`, or if `DATA` has a non-empty
`Error`, `error`, `ErrorMessage` or `error_message` other than `0`/`false`
(`client.py:170-186`). Slow Controls payloads are JSON in `DATA/JSON`
(`client.py:66-72`, `:280-288`); `getDAQState` string fields that start with
`{` or `[` are parsed as JSON (`client.py:205-215`); `getRunInfo`'s `plugin`
field likewise (`client.py:191-200`); `getSystemMessages`' `systemMessages` is
URL-decoded and split on `|` into time/message pairs (`client.py:257-272`).

### 3.3 `getFEMacroList` parsing (CLT-006)

`client.py:290-354` splits each `FEMacros` value on `:` into
`supervisor:lid:class:uid` followed by repeated
`name:permissions:nIn:in...:nOut:out...`, with no tooltip field, and
`PublicMacro`/`PrivateMacro` values as `name:permissions:nIn:...:nOut:...`.
The fixture in `tests/test_otsdaq_client.py:108-110` uses the same format.
Other clients of the same response disagree:

| Client | Delimiter | Tooltip field | Date |
|---|---|---|---|
| this package (`client.py:292`) | `:` | no | 2026-09-17 |
| `otsdaq-mu2e-calorimeter/UserWebGUI/html/Calorimeter_Test.html:167` | `:` | no | 2024 |
| `otsdaq-mu2e/UserWebGUI/js/Mu2eHardware.js:153`, `:173` | `;` | yes, URI-encoded, after permissions | 2026-06-26 |
| `mu2edaq-CFOControl` UDP path (`ots_mm_udp_interface.py:262-288`) | `;` | yes | — |

The string is built in otsdaq core, which is not in this superproject, so the
live format is not determined here.

### 3.4 Is it read-only?

- All requests are POST (`client.py:131`), as in the CRV web client.
- The 12 typed commands send only the getter RequestTypes in §1.2. None uses
  LID 281, so none carries a CookieCode. None uses the state-machine handler.
- Whether every getter is side-effect free is otsdaq-core behaviour. Not
  verified; `getSystemMessages` in particular may mark messages delivered.
- `raw` is unrestricted: `--handler state-machine` sends transitions,
  `raw runFEMacro --service macro` executes macros, LID 281 RequestTypes write
  configuration. It warns on stderr (`commands.py:228-231`) and proceeds
  without confirmation (CLT-007).

## 4. Authentication: CookieCode

- Sources: `MU2EDAQ_TOOLS_OTSDAQ_COOKIE`, else `cookie_file` from the
  file, profile or `MU2EDAQ_TOOLS_OTSDAQ_COOKIE_FILE` (`settings.py:208-210`).
  There is no command-line option and no YAML value for the code itself.
- File check: `stat()` follows symlinks; on POSIX any group or other permission
  bit (`mode & 0o077`) is refused, so 0600, 0400 and 0700 pass
  (`settings.py:85-88`; `tests/test_otsdaq_settings.py:119-127`). The owner is
  not checked, and Windows is not checked. An empty file is refused.
- The file is read for every `otsdaq` command, although only LID 281 requests
  use it, so a bad file fails every typed read (CLT-010).
- Transmission: added as form field `CookieCode` only when the LID is 281 and
  the caller did not supply one (`client.py:124-125`). It goes to whatever
  origin LID 281 resolves to, which `raw --lid 281 --service tfm` makes the TFM
  origin.
- Exposure through this package: error messages carry the cookie file path,
  never the value (`settings.py:84-94`); transport errors carry the URL, which
  holds only the query string (`client.py:138-142`); `mu2edaq-tools config`
  shows `cookie_file`, not the code. The package configures no logging. The
  code is held in `InstanceConfig.cookie_code`, a dataclass field included in
  its default `repr()` (`settings.py:26`); nothing prints that today.
  `raw --xml` prints whatever otsdaq returns; whether otsdaq echoes a refreshed
  CookieCode is not determined here. A hand-supplied `--form CookieCode=…` is
  visible in `ps` and shell history.
- The HOWTO's own setup steps (`doc/otsdaq-phase1-howto.md:224`, `:231`) type
  the code on a command line, which puts it in shell history, against its
  advice at `:248` (CLT-010).

## 5. TLS

`verify_tls` defaults to `False` in code (`config.py:42`) and in the reference
file (`config/mu2edaq-commandline-tools.yaml:35`). `requests_verify` is the CA
bundle path if set, else the flag (`settings.py:28-30`). When it is falsy, every
`otsdaq` command prints
`warning: TLS certificate verification is disabled for otsdaq instance <name>`
on stderr before the first request (`commands.py:131-136`) and suppresses
urllib3's per-request `InsecureRequestWarning` (`client.py:128-130`). The
documented tunnel (`doc/otsdaq-phase1-howto.md:173-178`) terminates TLS at
`localhost`, where a certificate issued for the otsdaq host cannot pass
hostname verification even with the right CA bundle. Severity reasoning is in
CLT-003 and `ARCHITECTURE.md`.

## 6. Python API

`man/man3/mu2edaq_commandline_tools.3`. Public names: `config.load`,
`config.find_config`, `config.config_search_paths`, `config.load_file`,
`config.load_env`, `config.DEFAULTS`, `cli.main`, `cli.COMMANDS`/`Command`;
`otsdaq.resolve_instance`, `InstanceConfig`, `OtsdaqClient`, `FEMacro`,
`OtsdaqResponse`, and the `OtsdaqError` hierarchy (`otsdaq/__init__.py:3-26`).
`OtsdaqClient.request()` is not restricted to getters.

## 7. C++ API

`man/man3/mu2edaq_cli_core.3`; header `src/include/mu2edaq_cli_core.hpp`.

```cpp
namespace mu2edaq::cli {
const char* version();          // MU2EDAQ_CLI_VERSION, parsed from __init__.py by CMake
const char* env_prefix();       // "MU2EDAQ_TOOLS_"
std::vector<std::string> config_search_paths(const std::string& explicit_path = "");
std::string find_config(const std::string& explicit_path = "");
std::string env_override(const std::string& key, const std::string& fallback = "");
}
```

CMake target `mu2edaq::cli_core` (shared or static per `BUILD_SHARED_LIBS`),
SOVERSION 0, installed with the header, the man pages and the reference YAML
(`CMakeLists.txt:26-47`, `:81-96`).

## 8. Files and environment

| Name | Read by | Purpose |
|---|---|---|
| `config/mu2edaq-commandline-tools.yaml` | Python (always, editable install), C++ when cwd is the checkout | reference config |
| `MU2EDAQ_TOOLS_CONFIG` | both | config file |
| `MU2EDAQ_TOOLS_{CLUSTER,DISCOVERY_TIMEOUT,LOG_LEVEL,LOG_DIR,COLOR}` | Python | unused settings (CLT-012) |
| `MU2EDAQ_TOOLS_LOG_DIR` | stop script | directory it deletes (CLT-002) |
| `MU2EDAQ_TOOLS_OTSDAQ_{INSTANCE,GATEWAY_URL,SLOW_CONTROLS_URL,TFM_URL,TIMEOUT,VERIFY_TLS,CA_BUNDLE,COOKIE_FILE}` | Python | otsdaq overrides |
| `MU2EDAQ_TOOLS_OTSDAQ_COOKIE` | Python | CookieCode value |
| `MU2EDAQ_TOOLS_PIDFILE` | start/stop scripts | pidfile path, default `.mu2edaq-tools.pid` |
| `PYTHON` | `bootstrap.sh` | interpreter |
| `data/otsdaq-femacros.json` | written by `extract-femacros.py` | static FE-macro inventory |

## 9. Review facts verified

- Python suite: 51 passed on Python 3.12.1 and on 3.9.6 (`/usr/bin/python3`,
  fresh venv with PyYAML, requests, pytest). All sources parse with the 3.9
  grammar.
- C++: out-of-tree CMake build; `ctest` 2/2 passed; `test_cli_core` ran
  5 CppUnit tests.
- The Python/C++ cases in §2.3 and the TFM derivation in §3.1 were run.
- The start script's pidfile survives `exec` (reproduced with the same
  `trap … EXIT; exec` pattern).
- `mu2edaq-discovery` is not imported or contacted; CONTRACT §9.5 (string
  `meta` values) does not apply.
