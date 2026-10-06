# Staged issues: mu2edaq-commandline-tools

Findings from the September 2026 DAQ mega-review (`mu2e-sept-mega-review`),
reviewed 2026-10-06 against `21420c9`.

**Why staged.** Per CONTRACT §9.1 no GitHub write was attempted. Each block
below is the §6 issue body, parsed by `docs/mega-review/tools/stage_issues.py`.
Route: `Mu2e/mu2edaq-commandline-tools` (public, issues enabled).

**Dedup.** `gh issue list -R Mu2e/mu2edaq-commandline-tools --state all`
returned **0 issues** on 2026-10-06.

**Fingerprints** are `sha1("Mu2e/mu2edaq-commandline-tools:<path>:<rule_id>")[:8]`,
no line number. **Labels:** `mega-review` plus the category shown.

14 entries: 2 × S2, 7 × S3, 5 × S4.

| ID | Sev | Category | rule_id | Fingerprint | Title |
|---|---|---|---|---|---|
| CLT-001 | S2 | bug | `tfm-fixed-port-collision` | `bf64b95e` | [otsdaq] every profile derives the same TFM origin, so daq-state for one subsystem can silently read another's |
| CLT-002 | S2 | bug | `stop-rmrf-env-logdir` | `9bd063a8` | [lifecycle] the stop script rm -rf's whatever MU2EDAQ_TOOLS_LOG_DIR names, which is also the documented log_dir override |
| CLT-003 | S3 | bug | `verify-tls-default-off` | `9ce11c1c` | [tls] certificate verification is off by default for every otsdaq request |
| CLT-004 | S3 | bug | `config-search-divergence` | `a38ffbb8` | [config] Python and C++ choose different config files from the same directory, contrary to the package's stated premise |
| CLT-005 | S3 | bug | `pidfile-trap-lost-on-exec` | `9ddbff77` | [lifecycle] exec discards the EXIT trap, so the pidfile outlives every run and stop signals a recycled PID |
| CLT-006 | S3 | bug | `femacros-format-disagreement` | `be09e8ab` | [otsdaq] macros parses FEMacros as colon-separated with no tooltip; the newer otsdaq-mu2e client parses semicolons with a tooltip |
| CLT-007 | S3 | enhancement | `raw-unrestricted-write` | `cd22d521` | [otsdaq] raw can drive state transitions, FE macros and configuration writes with no opt-in beyond a warning |
| CLT-008 | S3 | documentation | `otsdaq-origin-docs-disagree` | `844401e7` | [docs] otsdaq examples disagree with the shifter tunnel on scheme, ports and forwarded services |
| CLT-009 | S3 | enhancement | `no-ci` | `52049285` | [ci] 51 pytest cases and 5 CppUnit checks with no CI workflow |
| CLT-010 | S4 | bug | `cookie-hygiene` | `d3ed4e60` | [auth] CookieCode hygiene: read on every command, kept in InstanceConfig repr, owner unchecked, HOWTO puts it in shell history |
| CLT-011 | S4 | bug | `config-errors-unhandled` | `852edb40` | [config] a mistyped -c path is silently ignored and a YAML syntax error ends in a traceback |
| CLT-012 | S4 | documentation | `unused-global-options` | `c65897ce` | [config] five global options are parsed, documented and shown but have no effect |
| CLT-013 | S4 | enhancement | `no-dotenv` | `3596cd96` | [config] no .env layer in the precedence chain |
| CLT-014 | S4 | bug | `install-config-unsearched` | `9ade35a4` | [install] cmake --install writes the reference config to a path neither search list reads |

---

## CLT-001

**Title:** `[otsdaq] every profile derives the same TFM origin, so daq-state for one subsystem can silently read another's`

**Severity:** S2 — production breakage or silent wrong behaviour; workaround exists
**Category:** bug
**Location:** `src/mu2edaq_commandline_tools/otsdaq/settings.py:183`
**Found by:** mega-review (`mu2e-sept-mega-review`), 2026-10-06

## What
When a profile has no `tfm_url`, the TFM origin (LID 302, used by `daq-report`
and `daq-state`) is derived as the gateway host on the fixed port 3047. Every
profile on the same host, or tunnelled to `localhost`, therefore resolves to
the same TFM, and the output is labelled with the requested instance.

## Evidence
```
$ sed -n '183p' src/mu2edaq_commandline_tools/otsdaq/settings.py
    tfm = merged.get("tfm_url") or _with_port(gateway, 3047)
```
With the HOWTO's own multi-instance example (`doc/otsdaq-phase1-howto.md:119-128`):
```
crv     https://localhost:3075 https://localhost:3076 https://localhost:3047
tracker https://localhost:3175 https://localhost:3176 https://localhost:3047
calo    https://localhost:3275 https://localhost:3276 https://localhost:3047
```
(`resolve_instance()` output, run in this review.) The 3047 constant comes from
the CRV web client, `otsdaq-mu2e-crv/UserWebGUI/js/mu2e.js:9`
(`const TFM_PORT = 3047`). On site, the shifter docs put every subsystem's
otsdaq on `mu2e-cfo-01` at different gateway ports (3075 shift, 3085 CRV, 3065
tracker, 3025 calorimeter, ...; `mu2edaq-operations/shifter/docs/connecting.md:87-103`),
so direct access collides the same way.

## Why it matters
`mu2edaq-tools otsdaq daq-state --instance tracker` returns whatever artdaq
state the CRV (or any) TFM on 3047 reports, under the name "tracker", with exit
0. A shifter checking one subsystem sees another's run state. Slow Controls
does not have this problem because it is derived as gateway port + 1.

## Suggested fix
Do not derive a TFM origin when the gateway is not the CRV one: require
`tfm_url` per profile (fail with "tfm_url is not set for instance X") or make
the TFM port a per-profile key with no default. Update the HOWTO example to set
`tfm_url` for every profile, and change
`tests/test_otsdaq_settings.py::test_profile_and_service_url_derivation`
accordingly.

## Related
- CLT-008 (the examples' ports and tunnel)

<!-- mega-review-fingerprint: bf64b95e -->

---

## CLT-002

**Title:** `[lifecycle] the stop script rm -rf's whatever MU2EDAQ_TOOLS_LOG_DIR names, which is also the documented log_dir override`

**Severity:** S2 — production breakage or silent wrong behaviour; workaround exists
**Category:** bug
**Location:** `stop-mu2edaq-commandline-tools.sh:17`
**Found by:** mega-review (`mu2e-sept-mega-review`), 2026-10-06

## What
`stop-mu2edaq-commandline-tools.sh` deletes, recursively and without
confirmation, the directory named by `MU2EDAQ_TOOLS_LOG_DIR`. The same variable
is the documented environment override of the tools' `log_dir` setting. No
tool in the package writes logs, so the directory holds nothing the package
created.

## Evidence
```
$ grep -n 'LOGDIR\|rm -rf' stop-mu2edaq-commandline-tools.sh
17:LOGDIR="${MU2EDAQ_TOOLS_LOG_DIR:-$HERE/logs}"
53:find "$HERE" -name '__pycache__' -type d -prune -exec rm -rf {} + 2>/dev/null || true
54:if [ "$KEEP_LOGS" = 0 ] && [ -d "$LOGDIR" ]; then
55:    echo "==> Removing $LOGDIR"
56:    rm -rf "$LOGDIR"
$ grep -n 'LOG_DIR' README.md
115:| `log_dir` | `MU2EDAQ_TOOLS_LOG_DIR` | `--log-dir` | `logs` |
```
`config/mu2edaq-commandline-tools.yaml:21` describes `log_dir` as "Directory for
log files, relative to the working directory unless absolute". A relative value
is resolved against the caller's current directory; `MU2EDAQ_TOOLS_LOG_DIR=.`
deletes the current directory's contents.

## Why it matters
An operator who sets the documented variable to a shared log directory (for
example in a shell profile used by other DAQ tools) loses that directory the
next time anyone runs the stop script. Not S1 because the default target is the
checkout's own `logs/`, which nothing populates, and the loss requires the
variable to be set; `--keep-logs` avoids it.

## Suggested fix
Remove the log deletion: the package has no logs. If it is kept, delete only
`$HERE/logs`, never a path taken from the environment, and only files the
package wrote.

## Related
- CLT-012 (`log_dir` has no effect on the tools themselves)

<!-- mega-review-fingerprint: 9bd063a8 -->

---

## CLT-003

**Title:** `[tls] certificate verification is off by default for every otsdaq request`

**Severity:** S3 — correctness or maintainability risk, no current outage
**Category:** bug
**Location:** `src/mu2edaq_commandline_tools/config.py:42`
**Found by:** mega-review (`mu2e-sept-mega-review`), 2026-10-06

## What
`verify_tls` defaults to `False` in code and in the shipped reference config.
Every `otsdaq` command, including `raw`, connects without verifying the
server certificate unless the operator sets `verify_tls: true`, passes
`--verify-tls`, or configures a CA bundle.

## Evidence
```
$ sed -n '42p' src/mu2edaq_commandline_tools/config.py; sed -n '35p' config/mu2edaq-commandline-tools.yaml
    "verify_tls": False,
  verify_tls: false
$ sed -n '131,136p' src/mu2edaq_commandline_tools/otsdaq/commands.py
        if not instance.requests_verify:
            print(
                "warning: TLS certificate verification is disabled for otsdaq instance %s"
```

## Why it matters
An on-path party can impersonate the otsdaq server. On the default paths the
consequence is forged read-only output, not credential loss: no typed read
attaches the CookieCode (`client.py:124` adds it only for LID 281, which no typed
read uses). The exposure becomes credential theft when an operator configures a
CookieCode and uses `raw --lid 281`, or points `gateway_url` straight at an
otsdaq host across the DAQ network instead of an SSH local forward.

The rubric's anchor for "`verify_tls: false` shipped as the default" is S2.
This is filed one level lower for three reasons: the default path carries no
credential and cannot change run state; the documented deployment
(`doc/otsdaq-phase1-howto.md:173-178`) terminates TLS on `localhost` at an SSH
forward, so the unverified segment is loopback plus the gateway-to-otsdaq leg
inside the DAQ network; and the default is documented (README, HOWTO, man page,
config comment) and announced on stderr on every run. Raise to S2 if direct
gateway URLs or LID 281 use become routine.

Two related gaps: `http://` origins are accepted (`settings.py:45`), so a
CookieCode can go in clear text, and the warning then talks about TLS
verification, not the missing TLS. And `verify_tls: true` cannot pass hostname
verification through the documented tunnel, because the URL host is
`localhost`, so the advertised fix does not work for the main deployment
without a certificate that names `localhost`.

## Suggested fix
Default `verify_tls` to true and make the insecure mode an explicit
per-profile `verify_tls: false`. Refuse to send a CookieCode over `http://` or
with verification off. Document how to verify through a tunnel (a certificate
with a `localhost` SAN, or a configurable server name for the TLS handshake).

## Related
- CLT-010 (CookieCode handling)
- Mu2e/mu2edaq-phone-notification-system PNS-014 (hard-wired skip-verify, S2)

<!-- mega-review-fingerprint: 9ce11c1c -->

---

## CLT-004

**Title:** `[config] Python and C++ choose different config files from the same directory, contrary to the package's stated premise`

**Severity:** S3 — correctness or maintainability risk, no current outage
**Category:** bug
**Location:** `src/cpp/mu2edaq_cli_core.cpp:36`
**Found by:** mega-review (`mu2e-sept-mega-review`), 2026-10-06

## What
The header and README state that a C++ tool and a Python tool started from the
same directory read the same YAML file. They do not: the Python list has an
extra entry (the package's own `config/` file, which always exists under the
editable install), and only Python expands `~` in `-c` and
`MU2EDAQ_TOOLS_CONFIG`. The C++ library also has no YAML parser, no defaults
and no command-line layer, so it cannot apply the precedence rule at all.

## Evidence
```
$ sed -n '4,6p' src/include/mu2edaq_cli_core.hpp
// The config file lookup here mirrors mu2edaq_commandline_tools.config in the
// Python package, so a C++ tool and a Python tool started from the same place
// read the same YAML file.
$ sed -n '130p' src/mu2edaq_commandline_tools/config.py
    yield Path(__file__).resolve().parents[2] / "config" / "mu2edaq-commandline-tools.yaml"
```
Run in this review from a directory with no config file, `HOME` holding
`.config/mu2edaq/commandline-tools.yaml`:
```
python (editable): <checkout>/config/mu2edaq-commandline-tools.yaml
mu2edaq-tools-info: $HOME/.config/mu2edaq/commandline-tools.yaml
```
With `MU2EDAQ_TOOLS_CONFIG='~/site.yaml'`: Python reads `~/site.yaml`; the C++
side skips the literal `~/site.yaml` and reports
`$HOME/.config/mu2edaq/commandline-tools.yaml`.

## Why it matters
The package's premise (one config, one precedence, both languages) is false
for the most common case: an editable install run from any directory other
than the checkout. No C++ tool other than the diagnostic exists yet, so nothing
is broken today; the first C++ tool will read different settings from the
Python tools without any error. The tests check each side alone.

## Suggested fix
Make the two lists identical: either drop the package-relative entry from
Python or add it to C++ (the C++ side can take it from a compile definition),
and expand a leading `~` in C++. Add a test that runs `mu2edaq-tools config
--json` and `mu2edaq-tools-info` from the same scratch directory and compares
the chosen path. Correct the header comment and `README.md:11-13` to say the
C++ library locates the file only.

## Related
- CLT-014 (the installed config path is on neither list)

<!-- mega-review-fingerprint: a38ffbb8 -->

---

## CLT-005

**Title:** `[lifecycle] exec discards the EXIT trap, so the pidfile outlives every run and stop signals a recycled PID`

**Severity:** S3 — correctness or maintainability risk, no current outage
**Category:** bug
**Location:** `start-mu2edaq-commandline-tools.sh:41`
**Found by:** mega-review (`mu2e-sept-mega-review`), 2026-10-06

## What
The start script writes its PID, installs an EXIT trap to remove the pidfile,
and then `exec`s Python. `exec` replaces the shell, so the trap never runs and
the pidfile is left behind after every invocation.

## Evidence
```
$ sed -n '41,44p' start-mu2edaq-commandline-tools.sh
echo $$ > "$PIDFILE"
trap 'rm -f "$PIDFILE"' EXIT

exec "$VPY" -m mu2edaq_commandline_tools.cli "$@"
$ sed -n '31,35p' stop-mu2edaq-commandline-tools.sh
if [ -f "$PIDFILE" ]; then
    PID=$(cat "$PIDFILE")
    if [ -n "$PID" ] && kill -0 "$PID" 2>/dev/null; then
        echo "==> Stopping mu2edaq-tools (pid $PID)"
        kill -TERM "$PID" 2>/dev/null || true
```
Reproduced with the same `echo $$ > f; trap 'rm -f f' EXIT; exec true`
sequence: the file remains.

## Why it matters
After a normal run the pidfile names a PID that the kernel will reuse. The stop
script checks only `kill -0` and then sends SIGTERM and SIGKILL to whatever
process of the same user holds it. The window is long on Linux
(`pid_max` 4194304) and short on macOS (99999). Not S2 because PID reuse
within the window is unlikely on the Linux DAQ nodes.

## Suggested fix
For a one-shot tool, drop the pidfile. If a long `--watch` needs stopping, run
Python as a child (no `exec`), `wait` on it in the trap-protected shell, and in
the stop script check the process's command line before signalling it.

## Related
- CLT-002

<!-- mega-review-fingerprint: 9ddbff77 -->

---

## CLT-006

**Title:** `[otsdaq] macros parses FEMacros as colon-separated with no tooltip; the newer otsdaq-mu2e client parses semicolons with a tooltip`

**Severity:** S3 — correctness or maintainability risk, no current outage
**Category:** bug
**Location:** `src/mu2edaq_commandline_tools/otsdaq/client.py:292`
**Found by:** mega-review (`mu2e-sept-mega-review`), 2026-10-06

## What
`OtsdaqClient.macro_list()` splits each `getFEMacroList` `FEMacros` value on
`:` and expects `name:permissions:nIn:...:nOut:...` per macro. The most recent
web client of the same response in this superproject splits on `;` and reads
a URI-encoded tooltip after the permission field. This review cannot determine
which format the deployed otsdaq emits.

## Evidence
```
$ sed -n '292p;305p' src/mu2edaq_commandline_tools/otsdaq/client.py
        tokens = value.split(":")
            name, permissions = tokens[index : index + 2]
$ sed -n '153p;172p' ../otsdaq-mu2e/UserWebGUI/js/Mu2eHardware.js
					macroVar = macroVar.split(";");
							"tooltip": decodeURIComponent(macroVar[c + 2]),
$ sed -n '167p' ../otsdaq-mu2e-calorimeter/UserWebGUI/html/Calorimeter_Test.html
                        macroVar = macroVar.split(":");
```
`Mu2eHardware.js` was added 2026-06-26 (`b37c1e37`); `Calorimeter_Test.html` is
from 2024. `mu2edaq-CFOControl`'s UDP client of the same Macro Maker also
parses `;` with a tooltip (`mu2edaq-CFOControl/docs/INTERFACES.md` §2.1, which
flagged this disagreement for this package). The unit-test fixture uses the
colon format (`tests/test_otsdaq_client.py:108-110`).

## Why it matters
If the deployed otsdaq emits the semicolon format, `mu2edaq-tools otsdaq macros`
fails every time with a protocol error ("truncated FEMacros record" or
"invalid FE macro LID"); if a tooltip contains `:`, records are mis-split. The
macro inventory is the input for the planned FE-macro CLI
(`doc/otsdaq-command-surface.md` §5.1). Filed at S3 rather than S2 because the
live format is unverified.

## Suggested fix
Capture one live response with
`mu2edaq-tools otsdaq raw getFEMacroList --service macro --xml`, commit it as a
test fixture, and make the parser follow it (detect `;` vs `:` and the tooltip
field if both formats exist across otsdaq versions).

## Related
- `mu2edaq-CFOControl/docs/INTERFACES.md` §2.1

<!-- mega-review-fingerprint: be09e8ab -->

---

## CLT-007

**Title:** `[otsdaq] raw can drive state transitions, FE macros and configuration writes with no opt-in beyond a warning`

**Severity:** S3 — correctness or maintainability risk, no current outage
**Category:** enhancement
**Location:** `src/mu2edaq_commandline_tools/otsdaq/commands.py:227`
**Found by:** mega-review (`mu2e-sept-mega-review`), 2026-10-06

## What
`mu2edaq-tools otsdaq raw` posts any RequestType to any LID, with
`--handler state-machine` for run-control transitions. It prints a warning on
stderr and sends the request. There is no confirmation, flag or environment
gate, in a package and subcommand presented as read-only.

## Evidence
```
$ sed -n '228,231p' src/mu2edaq_commandline_tools/otsdaq/commands.py
    print(
        "warning: raw otsdaq requests are unrestricted and may change a live DAQ system",
        file=sys.stderr,
    )
$ grep -in 'read-only' README.md config/mu2edaq-commandline-tools.yaml src/mu2edaq_commandline_tools/otsdaq/__init__.py
config/mu2edaq-commandline-tools.yaml:27:# Read-only otsdaq client settings. The selected instance can be overridden
README.md:185:Phase 1 provides modeled, read-only access to run-control state, run info,
src/mu2edaq_commandline_tools/otsdaq/__init__.py:1:"""Read-only otsdaq HTTP client support."""
```
`mu2edaq-tools otsdaq raw Halt --handler state-machine` (or `runFEMacro` at LID
800) is one command away from `raw getAppStatus`. The README does say raw "can
modify or interrupt a live DAQ system" (`README.md:211-214`).

## Why it matters
A mistyped RequestType or a pasted command from a notes file can halt a run or
execute an FE macro on hardware. Whether otsdaq accepts the request without a
CookieCode depends on the instance's security mode, which this package does
not control.

## Suggested fix
Require an explicit opt-in for anything other than known getters: e.g.
`--allow-write` on the command line, refused unless also enabled by
`otsdaq.allow_raw_write: true` or an environment variable, and an interactive
confirmation when stdin is a TTY. Keep `raw` with getter RequestTypes
ungated.

## Related
- CLT-003

<!-- mega-review-fingerprint: cd22d521 -->

---

## CLT-008

**Title:** `[docs] otsdaq examples disagree with the shifter tunnel on scheme, ports and forwarded services`

**Severity:** S3 — correctness or maintainability risk, no current outage
**Category:** documentation
**Location:** `doc/otsdaq-phase1-howto.md:173`
**Found by:** mega-review (`mu2e-sept-mega-review`), 2026-10-06

## What
This package's HOWTO, README, man page and HTML guide configure `crv` as
`https://localhost:3075` through `-L 3075:OTSDAQ_HOST:8443`, with Slow Controls
on 3076 and TFM on 3047. The shifter documentation tunnels `localhost:3075` to
`mu2e-cfo-01:3075`, calls it the shift GUI, links it as `http://`, puts CRV on
3085, and forwards neither gateway port + 1 nor 3047. The two cannot both
describe the live system; this review does not know which does.

## Evidence
```
$ sed -n '173,178p' doc/otsdaq-phase1-howto.md
ssh \
  -L 3075:OTSDAQ_HOST:8443 \
  -L 3076:OTSDAQ_HOST:8444 \
  -L 3047:OTSDAQ_HOST:3047 \
  USER@LOGIN_HOST
$ grep -n '3075\|3085' ../mu2edaq-operations/shifter/docs/connecting.md | head -3
91:    LocalForward 3075 mu2e-cfo-01:3075     # shift GUI
93:    LocalForward 3085 mu2e-cfo-01:3085     # CRV
120:  -L 3075:mu2e-cfo-01:3075 \
$ grep -n 'localhost:3075' ../mu2edaq-operations/shifter/docs/ots/README.md
15:| **Remote** (via SSH tunnel) | [localhost:3075/urn:xdaq-application:lid=200](http://localhost:3075/urn:xdaq-application:lid=200) |
```

## Why it matters
A shifter following this package's docs with the standard shifter tunnel gets
a TLS error against an HTTP server (if 3075 is plain HTTP), reads the shift
instance when asking for CRV, and gets connection refused from every Slow
Controls and TFM command because those ports are not forwarded.

## Suggested fix
Confirm the scheme and ports of each otsdaq instance on `mu2e-cfo-01`, then
make the HOWTO, README, `man/man1/mu2edaq-otsdaq.1` and `html/setup.html` use
them, with one profile per subsystem, explicit `slow_controls_url` and
`tfm_url`, and the matching `LocalForward` lines added to the shifter docs.

## Related
- CLT-001

<!-- mega-review-fingerprint: 844401e7 -->

---

## CLT-009

**Title:** `[ci] 51 pytest cases and 5 CppUnit checks with no CI workflow`

**Severity:** S3 — correctness or maintainability risk, no current outage
**Category:** enhancement
**Location:** `.github/workflows`
**Found by:** mega-review (`mu2e-sept-mega-review`), 2026-10-06

## What
The package has a working Python suite and a CTest suite but no CI.

## Evidence
```
$ ls .github
ls: .github: No such file or directory
$ PYTHONPATH=src python3 -m pytest -q
51 passed
$ ctest --test-dir build
100% tests passed, 0 tests failed out of 2
```
Both pass on Python 3.12.1 and 3.9.6 in this review.

## Why it matters
Nothing runs the tests on push, so the Python 3.9 floor (AlmaLinux 9) and the
C++ build are checked only when someone remembers. CLT-004's cross-language
comparison would need CI to stay true.

## Suggested fix
Add `.github/workflows/ci.yml`: Python 3.9 and 3.12 on ubuntu and macOS running
`pip install -e .[dev] && pytest`, and a CMake configure/build/ctest job.

## Related
- Suite-wide tracking issue in `Mu2e/mu2edaq-main` (no CI on packages with test suites)

<!-- mega-review-fingerprint: 52049285 -->

---

## CLT-010

**Title:** `[auth] CookieCode hygiene: read on every command, kept in InstanceConfig repr, owner unchecked, HOWTO puts it in shell history`

**Severity:** S4 — cosmetic, stale, hygiene
**Category:** bug
**Location:** `src/mu2edaq_commandline_tools/otsdaq/settings.py:208`
**Found by:** mega-review (`mu2e-sept-mega-review`), 2026-10-06

## What
The CookieCode path is mostly sound (no CLI option, no YAML value, 0600-style
file check, sent only with LID 281, never in error messages). Four smaller
gaps remain:

1. The cookie file is read for every `otsdaq` command (`settings.py:208-210`),
   although no typed read uses LID 281; a wrong mode or path fails every read.
2. `InstanceConfig.cookie_code` is a plain dataclass field (`settings.py:26`),
   so `repr(instance)` prints the code. Nothing prints it today.
3. The file check (`settings.py:85`) tests only `mode & 0o077`; it does not
   check the owner, and is skipped on Windows.
4. The HOWTO tells the operator to type the code on a command line
   (`doc/otsdaq-phase1-howto.md:224`, `:231`), which puts it in shell history,
   three paragraphs before telling them not to (`:248`); `README.md:121-123`
   says the environment variable keeps it out of command history.

## Evidence
```
$ sed -n '208,210p' src/mu2edaq_commandline_tools/otsdaq/settings.py
    cookie = environ.get("MU2EDAQ_TOOLS_OTSDAQ_COOKIE") or _read_cookie(
        merged.get("cookie_file")
    )
$ sed -n '224p;231p' doc/otsdaq-phase1-howto.md
export MU2EDAQ_TOOLS_OTSDAQ_COOKIE='COOKIE_VALUE'
printf '%s\n' 'COOKIE_VALUE' > ~/.config/mu2edaq/crv-cookie
```

## Why it matters
Each is a small step towards the credential leaking or towards an unrelated
configuration error breaking read-only use. The CookieCode grants
Configuration Supervisor writes.

## Suggested fix
Read the file lazily, only when a LID 281 request is built. Declare
`cookie_code: Optional[str] = field(default=None, repr=False)`. Check
`st_uid == os.getuid()`. In the HOWTO, use `read -rs` or an editor to write the
file, and `read -rs MU2EDAQ_TOOLS_OTSDAQ_COOKIE; export ...` for the
environment.

## Related
- CLT-003

<!-- mega-review-fingerprint: d3ed4e60 -->

---

## CLT-011

**Title:** `[config] a mistyped -c path is silently ignored and a YAML syntax error ends in a traceback`

**Severity:** S4 — cosmetic, stale, hygiene
**Category:** bug
**Location:** `src/mu2edaq_commandline_tools/cli.py:144`
**Found by:** mega-review (`mu2e-sept-mega-review`), 2026-10-06

## What
`-c FILE` with a nonexistent `FILE` uses the built-in defaults with no message
(the man page now documents this). A YAML syntax error raises
`yaml.YAMLError`, which `main()` does not catch.

## Evidence
```
$ mu2edaq-tools -c nope.yaml config --json   # exit 0
{"config_file": null, ...}
$ sed -n '144p' src/mu2edaq_commandline_tools/cli.py
    except (OSError, ValueError, RuntimeError) as exc:
$ printf 'cluster: [unclosed\n' > bad.yaml; mu2edaq-tools -c bad.yaml config
Traceback (most recent call last):
...
yaml.parser.ParserError: while parsing a flow sequence
```

## Why it matters
An explicit path that is ignored hides a typo until a later command fails for
a different-looking reason ("no otsdaq instance selected"). The traceback is
noise for an operator. The C++ `mu2edaq-tools-info -c` behaves the same way on
a missing file.

## Suggested fix
Treat a missing explicit `-c` path as an error (exit 1). Catch `yaml.YAMLError`
alongside the others and print `<file>: <message>`.

## Related
- none

<!-- mega-review-fingerprint: 852edb40 -->

---

## CLT-012

**Title:** `[config] five global options are parsed, documented and shown but have no effect`

**Severity:** S4 — cosmetic, stale, hygiene
**Category:** documentation
**Location:** `src/mu2edaq_commandline_tools/cli.py:99`
**Found by:** mega-review (`mu2e-sept-mega-review`), 2026-10-06

## What
`--cluster`, `--discovery-timeout`, `--log-level`, `--log-dir` and
`--color/--no-color` (and their `MU2EDAQ_TOOLS_*` and YAML forms) are resolved
and shown by `mu2edaq-tools config`, but no subcommand reads them.

## Evidence
```
$ grep -rnE '"(cluster|discovery_timeout|log_level|log_dir|color)"' src/mu2edaq_commandline_tools
src/mu2edaq_commandline_tools/config.py:52:    "cluster": "mu2edaq",
...
src/mu2edaq_commandline_tools/cli.py:140:        "color": args.color,
$ grep -rn 'import logging' src/mu2edaq_commandline_tools
$
```
Every hit is a definition (`config.py:52-56`), a coercion (`config.py:63-64`),
the parser (`cli.py:99-116`) or the override dict passed to `config.load`
(`cli.py:135-141`); nothing reads the resolved values. No module imports
`logging`. The help text promises "seconds to wait for discovery responses"
(`cli.py:103`).

## Why it matters
Operators can set options that change nothing, and the stop script deletes the
directory named by the `log_dir` variable (CLT-002).

## Suggested fix
Either remove the five settings until a tool uses them, or mark them
"reserved, no effect" in `--help`, the README table and the YAML comments.

## Related
- CLT-002

<!-- mega-review-fingerprint: c65897ce -->

---

## CLT-013

**Title:** `[config] no .env layer in the precedence chain`

**Severity:** S4 — cosmetic, stale, hygiene
**Category:** enhancement
**Location:** `src/mu2edaq_commandline_tools/config.py:3`
**Found by:** mega-review (`mu2e-sept-mega-review`), 2026-10-06

## What
The suite convention is command line > environment > `.env` > config file >
defaults. This package implements four layers with no `.env`, in both Python
and C++.

## Evidence
```
$ sed -n '3,8p' src/mu2edaq_commandline_tools/config.py
Precedence, highest first:

    1. command line options
    2. environment variables (MU2EDAQ_TOOLS_*)
    3. YAML config file
    4. built-in defaults
```
A `.env` in the working directory containing `MU2EDAQ_TOOLS_CLUSTER=from-dotenv`
is ignored by both languages (verified).

## Why it matters
Consistency with the other suite packages; no operational consequence today.

## Suggested fix
Load `./.env` (stdlib parser, no dependency) between the environment and file
layers in Python, and in the C++ `env_override`, with the same search rule in
both.

## Related
- CLT-004

<!-- mega-review-fingerprint: 3596cd96 -->

---

## CLT-014

**Title:** `[install] cmake --install writes the reference config to a path neither search list reads`

**Severity:** S4 — cosmetic, stale, hygiene
**Category:** bug
**Location:** `CMakeLists.txt:94`
**Found by:** mega-review (`mu2e-sept-mega-review`), 2026-10-06

## What
`cmake --install` writes `config/mu2edaq-commandline-tools.yaml` to
`${CMAKE_INSTALL_SYSCONFDIR}/mu2edaq/commandline-tools.yaml`, which is
`${prefix}/etc/...`. Both search lists look only in `/etc/mu2edaq/`, so with
the default prefix `/usr/local` (or `/usr`, since the relative
`CMAKE_INSTALL_SYSCONFDIR` is used) the installed file is never read.

## Evidence
```
$ sed -n '94,96p' CMakeLists.txt
install(FILES config/mu2edaq-commandline-tools.yaml
  DESTINATION ${CMAKE_INSTALL_SYSCONFDIR}/mu2edaq
  RENAME commandline-tools.yaml)
$ grep -n '/etc/mu2edaq' src/mu2edaq_commandline_tools/config.py src/cpp/mu2edaq_cli_core.cpp
src/mu2edaq_commandline_tools/config.py:132:    yield Path("/etc/mu2edaq/commandline-tools.yaml")
src/cpp/mu2edaq_cli_core.cpp:58:  paths.push_back("/etc/mu2edaq/commandline-tools.yaml");
```

## Why it matters
An installed system silently runs on defaults. `mu2edaq-config`'s installer
writes a third, different path (`mu2edaq-config/docs/INTERFACES.md:103-109`,
CFG-005).

## Suggested fix
Install to `${CMAKE_INSTALL_FULL_SYSCONFDIR}` and add the same configured
directory to both search lists (compile definition for C++, a generated
module constant for Python), or document that `/etc/mu2edaq/` must be
populated by hand.

## Related
- Mu2e/mu2edaq-config CFG-005

<!-- mega-review-fingerprint: 9ade35a4 -->
