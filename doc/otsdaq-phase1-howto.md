# Phase 1 otsdaq Client: Testing and Usage HOWTO

This guide explains how to install, configure, test, and use the Phase 1
read-oriented otsdaq client in `mu2edaq-commandline-tools`.

Phase 1 provides modeled commands for reading:

- Run-control state and run information
- artdaq/TFM reports and process state
- The live FE-macro inventory
- Slow Controls PV names, values, settings, and alarms
- otsdaq console and system messages

The modeled commands do not execute FE macros, make state transitions, change
configuration, restart applications, or write PVs.

> **Important:** `mu2edaq-tools otsdaq raw` is an unrestricted expert
> interface. It is not read-only and can change or interrupt a running DAQ
> system.

## 1. Prerequisites

Supported platforms:

- macOS
- AlmaLinux 9 or a compatible Linux environment
- Python 3.9 or newer

Python dependencies are installed automatically by the bootstrap script:

- Requests
- PyYAML
- pytest when `--dev` is used

The optional C++ build requires:

- CMake 3.16 or newer
- A C++17 compiler
- CppUnit when available; an assert-based test driver is used otherwise

## 2. Install or update the tools

From the `mu2edaq-commandline-tools` checkout:

```bash
./bootstrap.sh --dev --cpp
source venv/bin/activate
```

For Python-only usage:

```bash
./bootstrap.sh --dev
source venv/bin/activate
```

Confirm the installation:

```bash
mu2edaq-tools --version
mu2edaq-tools list
mu2edaq-tools otsdaq --help
```

The expected package version is `0.2.0` or newer, and `otsdaq` should appear in
the command list.

Without activating the virtual environment, commands may be run through:

```bash
./start-mu2edaq-commandline-tools.sh otsdaq --help
```

## 3. Configure an otsdaq instance

Copy the annotated reference configuration or create a local configuration:

```bash
cp config/mu2edaq-commandline-tools.yaml mu2edaq-commandline-tools.yaml
```

Add at least one named instance:

```yaml
otsdaq:
  default_instance: crv
  timeout: 10.0

  # This is the Phase 1 default. See the TLS section before changing it.
  verify_tls: false
  ca_bundle: null

  instances:
    crv:
      gateway_url: https://localhost:3075
```

With this configuration:

- Gateway, Console, and Macro Maker use `https://localhost:3075`.
- Slow Controls is derived as `https://localhost:3076`.
- TFM is derived as `https://localhost:3047`.

Override derived service origins when the tunnel, proxy, or deployment uses
different ports:

```yaml
otsdaq:
  default_instance: crv
  instances:
    crv:
      gateway_url: https://localhost:3075
      slow_controls_url: https://localhost:4076
      tfm_url: https://localhost:4047
```

Multiple subsystem instances may be defined in the same file:

```yaml
otsdaq:
  default_instance: crv
  instances:
    crv:
      gateway_url: https://localhost:3075
    tracker:
      gateway_url: https://localhost:3175
    calo:
      gateway_url: https://localhost:3275
```

Select a non-default profile after the read command:

```bash
mu2edaq-tools otsdaq state --instance tracker
```

### Config file selection

The global `--config` option must appear before `otsdaq`:

```bash
mu2edaq-tools --config /path/to/tools.yaml otsdaq state
```

Inspect the effective configuration:

```bash
mu2edaq-tools config
mu2edaq-tools config --json
```

Configuration precedence is:

```text
command line > environment > YAML file > defaults
```

Useful environment overrides include:

```bash
export MU2EDAQ_TOOLS_OTSDAQ_INSTANCE=tracker
export MU2EDAQ_TOOLS_OTSDAQ_GATEWAY_URL=https://localhost:3175
export MU2EDAQ_TOOLS_OTSDAQ_TIMEOUT=15
export MU2EDAQ_TOOLS_OTSDAQ_VERIFY_TLS=true
```

### SSH tunnel example

A typical local profile uses ports 3075, 3076, and 3047. The corresponding
tunnel is conceptually:

```bash
ssh \
  -L 3075:OTSDAQ_HOST:8443 \
  -L 3076:OTSDAQ_HOST:8444 \
  -L 3047:OTSDAQ_HOST:3047 \
  USER@LOGIN_HOST
```

Replace hostnames and remote ports with the values for the target deployment.
Keep the SSH session open while using the client.

## 4. TLS and optional credentials

### TLS

Phase 1 defaults to disabled certificate verification because DAQ test
instances and SSH tunnels commonly use locally issued certificates. Each
network command prints this warning on stderr:

```text
warning: TLS certificate verification is disabled for otsdaq instance ...
```

JSON remains clean on stdout despite the warning.

Enable verification with any of:

```yaml
otsdaq:
  verify_tls: true
```

```bash
mu2edaq-tools otsdaq state --verify-tls
```

Or configure a CA bundle:

```yaml
otsdaq:
  ca_bundle: /path/to/daq-ca-bundle.pem
```

A CA bundle automatically enables verification.

### CookieCode

The modeled Phase 1 reads normally operate anonymously. If Configuration
Supervisor access through LID 281 needs an existing `CookieCode`, supply it
through the environment:

```bash
export MU2EDAQ_TOOLS_OTSDAQ_COOKIE='COOKIE_VALUE'
```

Or place it in an owner-only file:

```bash
install -m 600 /dev/null ~/.config/mu2edaq/crv-cookie
printf '%s\n' 'COOKIE_VALUE' > ~/.config/mu2edaq/crv-cookie
chmod 600 ~/.config/mu2edaq/crv-cookie
```

Then reference only the path:

```yaml
otsdaq:
  instances:
    crv:
      gateway_url: https://localhost:3075
      cookie_file: ~/.config/mu2edaq/crv-cookie
```

The configured cookie is sent only to LID 281. It is not sent to Gateway,
Macro Maker, Console, Slow Controls, or TFM requests.

Do not place a CookieCode directly in YAML, scripts, shell history, logs, or
bug reports.

## 5. Safe live-instance smoke test

Start with a development or non-production instance whenever possible. If only
a production instance is available, run only the modeled read commands in this
section.

### Step 1: Verify state access

```bash
mu2edaq-tools otsdaq state
mu2edaq-tools otsdaq state --json
```

The JSON response is an envelope:

```json
{
  "command": "state",
  "data": {
    "state": "Running"
  },
  "instance": "crv",
  "timestamp": "2026-07-27T20:00:00+00:00"
}
```

The exact fields inside `data` come from the running otsdaq version.

### Step 2: Read run and DAQ status

```bash
mu2edaq-tools otsdaq run-info
mu2edaq-tools otsdaq daq-report
mu2edaq-tools otsdaq daq-state
```

Read a historical run number:

```bash
mu2edaq-tools otsdaq run-info 105504 --json
```

### Step 3: Discover live macros without running them

```bash
mu2edaq-tools otsdaq macros
mu2edaq-tools otsdaq macros --json
```

The macro inventory depends on the active configuration. A configured DTC can
advertise additional forwarding macros for its child ROCs, so the live result
is authoritative.

An empty inventory can mean that the state machine has not been configured.
The `macros` command never invokes a macro.

### Step 4: Read Slow Controls

List PVs:

```bash
mu2edaq-tools otsdaq pv-list
```

Read one or more PVs:

```bash
mu2edaq-tools otsdaq pv-read \
  Mu2e:TDAQ_crv:daq08DTC:Temperature \
  Mu2e:TDAQ_crv:daq08DTC:Voltage
```

Read PV metadata/settings:

```bash
mu2edaq-tools otsdaq pv-settings \
  Mu2e:TDAQ_crv:daq08DTC:Temperature
```

Read alarms:

```bash
mu2edaq-tools otsdaq alarms
mu2edaq-tools otsdaq alarms Mu2e:TDAQ_crv:daq08DTC:Temperature
mu2edaq-tools otsdaq alarm-checks
```

### Step 5: Read logs and messages

```bash
mu2edaq-tools otsdaq console
mu2edaq-tools otsdaq console --lcount 100
mu2edaq-tools otsdaq messages
mu2edaq-tools otsdaq messages --history
```

## 6. Polling and scripting

All modeled read commands support polling:

```bash
mu2edaq-tools otsdaq state --watch
mu2edaq-tools otsdaq daq-state --watch --interval 1
mu2edaq-tools otsdaq pv-read PV_NAME --watch --interval 5
```

Stop unbounded polling with Ctrl-C. The command exits with status 130.

Use `--count` for a bounded run:

```bash
mu2edaq-tools otsdaq state \
  --watch \
  --interval 1 \
  --count 10
```

With `--json`, watch mode emits one complete JSON document per line (NDJSON):

```bash
mu2edaq-tools otsdaq daq-state \
  --watch \
  --interval 2 \
  --count 5 \
  --json > daq-state.ndjson
```

Process one-shot JSON with `jq` when it is installed:

```bash
mu2edaq-tools otsdaq state --json | jq '.data'
```

Process an NDJSON stream:

```bash
mu2edaq-tools otsdaq state --watch --json |
  jq --unbuffered '.timestamp, .data'
```

Console watch mode carries the server's returned message count into the next
request, avoiding repeated messages when the server provides a usable cursor.

## 7. Expert raw requests

The raw interface exposes arbitrary:

- LIDs
- RequestTypes
- Request and state-machine handlers
- Query parameters
- Form fields

It warns on every invocation:

```text
warning: raw otsdaq requests are unrestricted and may change a live DAQ system
```

Use it only after reviewing the target RequestType. It does not support watch
mode, which prevents accidental repeated writes.

A read-oriented example:

```bash
mu2edaq-tools otsdaq raw getAppStatus \
  --service gateway
```

Emit the exact XML response:

```bash
mu2edaq-tools otsdaq raw getAppStatus \
  --service gateway \
  --xml
```

Pass query or form values:

```bash
mu2edaq-tools otsdaq raw SomeRequest \
  --lid 200 \
  --query name=value \
  --form option=value
```

Do not use raw RequestTypes such as `runFEMacro`, configuration save/activate
operations, restart requests, or state-machine transitions during a Phase 1
read-only validation.

## 8. Run the automated tests

The Python tests include an in-process fake otsdaq harness. It starts separate
ephemeral loopback servers for:

- Gateway, Console, and Macro Maker
- Slow Controls
- TFM

It never contacts a live otsdaq system.

### Complete Python suite

```bash
./bootstrap.sh --dev
source venv/bin/activate
pytest -q
```

Expected result:

```text
51 passed
```

The harness must be allowed to bind ephemeral `127.0.0.1` ports. A restricted
container or sandbox may need explicit loopback-socket permission.

### Focused otsdaq tests

```bash
pytest -q \
  tests/test_otsdaq_settings.py \
  tests/test_otsdaq_client.py \
  tests/test_otsdaq_cli.py
```

Run one test while showing captured output:

```bash
pytest -vv -s tests/test_otsdaq_cli.py::test_state_json_and_watch_ndjson
```

The harness verifies:

- Named profiles and service URL derivation
- Environment and command-line precedence
- TLS, CA bundle, and protected cookie handling
- Correct origins, LIDs, query parameters, and form bodies
- XML normalization and embedded JSON parsing
- Runtime macro inventory parsing
- HTTP and protocol failures
- Human, JSON, NDJSON, watch, and raw behavior

### C++ regression suite

The Phase 1 otsdaq client is Python-only, but the existing C++ library must
continue to build:

```bash
cmake -S . -B build -DBUILD_TESTING=ON
cmake --build build
ctest --test-dir build --output-on-failure
```

Expected result:

```text
100% tests passed, 0 tests failed out of 2
```

### Packaging check

Build a wheel without installing it:

```bash
python3 -m pip wheel \
  --no-deps \
  --no-build-isolation \
  --wheel-dir /tmp/mu2edaq-commandline-tools-wheel \
  .
```

The output wheel should be named similarly to:

```text
mu2edaq_commandline_tools-0.2.0-py3-none-any.whl
```

## 9. Platform validation

### macOS

```bash
./bootstrap.sh --dev --cpp
source venv/bin/activate
pytest -q
ctest --test-dir build --output-on-failure
```

### AlmaLinux 9

Install Python 3.9+, pip, CMake, and a C++ compiler using the site's normal
package or development environment, then:

```bash
./bootstrap.sh --dev --cpp --python python3
source venv/bin/activate
python --version
pytest -q
ctest --test-dir build --output-on-failure
```

The implementation and tests avoid Python syntax newer than 3.9.

## 10. Exit statuses

| Status | Meaning |
|---:|---|
| 0 | Success |
| 1 | Configuration, connection, HTTP, XML, JSON, or otsdaq response failure |
| 2 | Invalid or missing command-line arguments |
| 130 | Watch mode interrupted with Ctrl-C |

Use exit status in scripts:

```bash
if mu2edaq-tools otsdaq state --json > state.json; then
  echo "state read succeeded"
else
  echo "state read failed" >&2
fi
```

## 11. Troubleshooting

### No otsdaq instance selected

```text
no otsdaq instance selected; set otsdaq.default_instance or use --instance
```

Set `otsdaq.default_instance`, pass `--instance NAME`, or supply a one-off
`--gateway-url`.

### Unknown instance

Confirm the profile exists under `otsdaq.instances` and inspect:

```bash
mu2edaq-tools config --json
```

### Connection refused or timeout

Check:

1. The otsdaq instance is running.
2. The SSH tunnel is still open.
3. Gateway, Slow Controls, and TFM use the expected ports.
4. A firewall is not blocking the connection.
5. `--timeout` is sufficient for the endpoint.

Try explicit origins when automatic derivation does not match the deployment:

```bash
mu2edaq-tools otsdaq state \
  --gateway-url https://localhost:3075 \
  --slow-controls-url https://localhost:3076 \
  --tfm-url https://localhost:3047
```

### Certificate verification failure

Prefer configuring the correct CA bundle:

```bash
mu2edaq-tools otsdaq state --ca-bundle /path/to/ca.pem
```

Use `--insecure` only when the target and network path are understood.

### Cookie file rejected

On macOS and AlmaLinux, make it owner-only:

```bash
chmod 600 ~/.config/mu2edaq/crv-cookie
```

### HTTP 404

Verify the selected profile points to the otsdaq HTTP origin rather than an
unrelated web server or proxy path. Configured origins must not contain a URL
path, query, or fragment.

### Invalid XML or missing DATA

The endpoint may have returned an HTML login page, proxy error, or a response
from a different otsdaq version. Capture exact XML only when safe:

```bash
mu2edaq-tools otsdaq raw READ_REQUEST_TYPE --lid LID --xml
```

Remove credentials and sensitive operational information before sharing the
response.

### Empty macro list

The running instance may not be configured yet. Macro discovery reflects the
active FE/ROC configuration and can legitimately change after Configure.

## 12. Phase 1 boundaries

The following are deliberately deferred:

- FE-macro execution
- Run-control transitions
- Configuration database writes or activation
- PV writes
- Supervisor restart actions
- Host-local firmware and setup scripts
- Standalone hardware test binaries
- Automated login or CookieCode acquisition

Use the typed Phase 1 commands for operational reads and treat `raw` as a
separate expert capability with write-level risk.
