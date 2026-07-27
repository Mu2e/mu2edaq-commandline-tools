# The otsdaq-mu2e Command Surface

**A survey of what the `otsdaq-*` packages expose, and how, as scoping input for
`mu2edaq-commandline-tools`.**

Status: survey complete, no code written yet.
Date: 2026-07-27.
Surveyed at: `mu2edaq-main` commit `1d2e013`, submodule tips as checked out on that date.

---

## 1. Why this document exists

We want a set of command line tools that work with the `otsdaq-*` packages. Before
designing them we need to know what "a command" even *is* in this stack, how many
there are, and by what route a non-browser client can invoke one. This document
answers those three questions and ends with a scope assessment.

It is a survey of the ten `otsdaq-mu2e*` submodules only. **The otsdaq core itself is
not vendored in this repo** — it is an external dependency (`otsdaq::`, `xdaq`,
`artdaq`) pulled in by spack/mrb. Everything below is what the *Mu2e* packages
define or call; where the core's behavior matters, it is inferred from call sites in
Mu2e code and flagged as such.

---

## 2. The packages at a glance

| Package | Files | What it contributes |
|---|---:|---|
| `otsdaq-mu2e` | 189 | The core: DTC/CFO front-end interfaces, ROC base classes, DCS, most FE macros |
| `otsdaq-mu2e-config` | 5806 | The configuration database — 11 subsystem `Data_*` trees, plus site setup scripts |
| `otsdaq-mu2e-tracker` | 242 | Tracker ROC interface, test-stand importer/generator, fcl |
| `otsdaq-mu2e-calorimeter` | 115 | Calorimeter ROC interface, board configs, calo web GUI |
| `otsdaq-mu2e-crv` | 83 | CRV ROC interface, **and `mu2e.js` — the reference HTTP client** |
| `otsdaq-mu2e-dqm` | 61 | DQM histogram consumers, fcl |
| `otsdaq-mu2e-trigger` | 59 | Trigger config/fcl |
| `otsdaq-mu2e-stm` | 52 | STM interface + GUI |
| `otsdaq-mu2e-extmon` | 52 | ExtMon interface + GUI |
| `otsdaq-mu2e-sync` | 23 | Mobile-sync ROC interface |

Note the shape: only five packages define runtime commands. `otsdaq-mu2e-config` is
data, and dqm/trigger/stm/extmon are mostly art configuration.

---

## 3. Six distinct exposure mechanisms

There is no single "command" concept. Six different things could reasonably be
called a command, and a CLI project has to decide which of them it targets. In rough
order of value to us:

| # | Mechanism | Count | Reachable remotely? | Notes |
|---|---|---:|---|---|
| A | **FE Macros** | 184 | Yes, over HTTP | The real command surface |
| B | **Supervisor request endpoints** | ~41 observed | Yes, over HTTP | The transport for everything else |
| C | **Run-control state transitions** | 6 | Yes, over HTTP | Configure/Start/Stop/Halt/Pause/Resume |
| D | **Slow controls / DCS (EPICS PVs)** | unbounded | Yes, separate port | Read/poll/alarms |
| E | **Shell scripts** (`tools/`) | ~50 | No — host-local | Firmware, install, snapshots |
| F | **Standalone C++ test binaries** | 6 | No — needs the PCIe device | Bypasses the running system |

### A. FE Macros — the primary command surface

An **FE Macro** is a C++ method on a front-end interface registered by name at
construction time, so it can be called by name later. This is otsdaq's mechanism for
"do a thing to this piece of hardware."

Registration looks like this (`CAPTANSignalGenerator_interface.cc:64`):

```cpp
registerFEMacroFunction(
    "Get Pulse Period",                                  // feMacroName
    static_cast<FEVInterface::frontEndMacroFunction_t>(
        &CAPTANSignalGenerator::getPulsePeriod),         // feMacroFunction
    std::vector<std::string>{},                          // namesOfInputArgs
    std::vector<std::string>{"Pulse Period (us)",        // namesOfOutputArgs
                             "Low Pulse Width (Clock Cycle := 10 ns)"},
    1,                                                   // requiredUserPermissions
    "*",                                                 // allowedCallingFEs
    "Returns the clock period of the pulse trigger ...");// description
```

So every macro carries its own name, typed-by-convention argument *names*, a
permission level, and optionally a human description. That metadata is what makes a
generated CLI feasible at all.

**Inventory: 184 active registrations** across five packages (a further 17
registrations exist but are commented out, and one apparent registration in
`otsdaq_import_tracker_test_stand.cc` is a false positive — that file is a *code
generator* that emits registration source).

| Package | Interface | Macros |
|---|---|---:|
| `otsdaq-mu2e` | `DTCFrontEndInterface` | 52 |
| `otsdaq-mu2e` | `CFOFrontEndInterface` | 26 |
| `otsdaq-mu2e` | `CFOandDTCCoreVInterface` | 11 |
| `otsdaq-mu2e` | `CAPTANSignalGenerator` | 7 |
| `otsdaq-mu2e` | `ROCPolarFireCoreInterface` | 5 |
| `otsdaq-mu2e` | `ROCCoreVInterface` | 2 |
| `otsdaq-mu2e-crv` | `ROCCosmicRayVetoInterface` | 42 |
| `otsdaq-mu2e-calorimeter` | `ROCCalorimeterInterface` | 25 |
| `otsdaq-mu2e-sync` | `ROCMobileSyncInterface` | 9 |
| `otsdaq-mu2e-tracker` | `ROCTrackerInterface` | 5 |
| | **Total** | **184** |

Quality of the metadata, which directly bounds how good a generated CLI can be:

- 182 of 184 have a literal string name (2 are built at runtime — see §5.1).
- **86 of 184 (47%) carry a description.** The other half are name-only.
- 112 declare input arguments, 120 declare outputs.
- Argument counts run from 0 to 14 (`CFO Emulator Fixed-width Event Window
  Emulation Setup`).
- Permission level is `1` on all but one. There is effectively **no privilege
  tiering** in the current registrations — "reset the DTC" and "read a register"
  are equally privileged.

A machine-readable dump of all 202 detected call sites (including the inactive ones,
flagged) ships alongside this document as
[`data/otsdaq-femacros.json`](../data/otsdaq-femacros.json), regenerated by
[`tools/extract-femacros.py`](../tools/extract-femacros.py).

### B. Supervisor request endpoints — the transport

Every xdaq supervisor exposes an HTTP endpoint addressed by **LID** (xdaq local ID).
The pattern, taken from `otsdaq-mu2e-crv/UserWebGUI/js/mu2e.js:27-67`:

```
POST {base}/urn:xdaq-application:lid={LID}/Request?RequestType={name}
     body: url-encoded parameters
  -> XML response, payload under the <ROOT>/<DATA> element
```

State machine transitions use a different path on the same supervisor:

```
POST {base}/urn:xdaq-application:lid=200/StateMachineXgiHandler?StateMachine={transition}
     body: ConfigurationAlias={alias}
```

The LIDs in use:

| LID | Supervisor | Base URL |
|---:|---|---|
| 200 | Gateway (run control, state machine, run info) | page origin |
| 260 | Console (log messages) | page origin |
| 281 | Configuration (table read/write, groups, aliases) | page origin |
| 282 | Slow Controls / DCS | **origin port + 1** |
| 302 | TFM (artdaq DAQ report/state) | **fixed port 3047** |
| 800 | Macro Maker (**runs FE macros**) | page origin |

~41 distinct `RequestType` values are observably used by the Mu2e GUIs. This is *not*
the complete otsdaq API — it is the subset Mu2e code happens to call. The ones that
matter most:

| RequestType | LID | Purpose |
|---|---:|---|
| `getFEMacroList` | 800 | **Enumerate available FE macros at runtime** |
| `runFEMacro` | 800 | **Execute one** |
| `getStateMachine`, `getStateMachineNames`, `getCurrentState` | 200 | Run control status |
| `getRunInfo` | 200 | Run number/metadata |
| `getDAQReport`, `getDAQState` | 302 | artdaq process state |
| `getTreeView`, `getSpecificTable`, `getTreeNodeFieldValues` | 281 | Read configuration |
| `saveSpecificTable`, `saveNewTableGroup`, `activateTableGroup` | 281 | Write/activate configuration |
| `getActiveTableGroups`, `setGroupAliasInActiveBackbone` | 281 | Group/alias management |
| `getList`, `getPVSettings`, `getPvData`, `generateUID`, `poll` | 282 | DCS PV access |
| `getLastAlarmsData`, `getAlarmsCheck` | 282 | Alarms |
| `GetConsoleMsgs` | 260 | Console log |
| `restartApps` | 200 | Restart a supervisor |

The exact `runFEMacro` call shape (`mu2e.js:722`):

```
POST .../lid=800/Request?RequestType=runFEMacro
     &feClassSelected=DTCFrontEndInterface
     &feUIDSelected=daq08DTC
     &macroType=fe
     &macroName=DTC%20Read
     &saveOutputs=0
body: inputArgs=address,0x9100&outputArgs=readData
```

Arguments are a flat `name,value` list, `;`-separated, with the **argument names
exactly as registered in C++** — including spaces, parentheses and units, e.g.
`Target ROC (Default = -1 := all ROCs),‑1`. This is the single most awkward part of
the protocol for a CLI to wrap (§5.2).

### C. Run-control state transitions

Six transitions drive the DAQ: **Initialize, Configure, Start, Stop, Pause, Resume,
Halt** (Configure/Start/Stop/Halt are the ones the Mu2e GUIs bind to buttons).
`Configure` takes a `ConfigurationAlias`; transitions are addressed to a named FSM
(`fsmName`, e.g. `CrvVstRun`).

Operationally this is layered: per `mu2edaq-operations/shifter/docs/ots/README.md`,
the Mu2e DAQ runs **multiple independent otsdaq instances** — a top-level "shift"
instance that orchestrates per-subsystem instances (`cfo`, `calo`, `tracker`, `crv`,
`stm`, `trigger`, `dqm`), each with its own inclusion mode and configuration alias.
A CLI has to be explicit about *which instance* it is talking to.

### D. Slow controls / DCS

EPICS-style process variables behind LID 282, named
`Mu2e:TDAQ_{subsystem}:{device}:{field}` — e.g.
`Mu2e:TDAQ_crv:daq08DTC:...`, `Mu2e:TDAQ_crv:{proc}:1:Fragment_Rate`. Two access
patterns: direct (`getPvData` with a PV list) and subscription-style
(`generateUID` to register a list, then `poll` against the returned uid). Alarms come
from `getLastAlarmsData`.

### E. Shell scripts (`otsdaq-mu2e/tools/`, ~50)

Host-local, not remotely invocable, and largely **not** in scope for a remote CLI —
but worth cataloguing because some are candidates for wrapping. Categories:

- **FPGA/firmware** (~20): `program_one_FPGA.sh`, `program_flash_both_DTCs.sh`,
  `boot_from_flash_all_DTCs_AL9.sh`, `erase_flash_both_DTCs.sh`,
  `check_firmware_version.sh`, plus paired `.tcl` for Vivado.
- **PCIe/JTAG reset**: `reset_PCIe.sh`, `reset_both_JAs_AL9.sh`, `find_JTAG_usb_AL9.sh`.
- **Install/bootstrap** (~8): `quick_mu2e_ots_install.sh`, `mu2e-quick-spack-start*.sh`,
  `distributed_setup_ots.sh`.
- **Snapshots** (~6): `create_mu2e_ots_snapshot.sh`, `get_mu2e_snapshot_data.sh`,
  `reset_mu2e_ops_snapshot.sh`.
- **Misc**: `post_to_ecl.sh` (logbook), `check_status.sh`, `collect.sh`.

These have inconsistent interfaces: most take positional arguments, few have
`--help`, several must be *sourced* rather than executed.

`otsdaq-mu2e-config` adds ~17 more site-setup scripts (`db_setup_ots.sh`,
`hwdev_setup_ots.sh`, `kinit_setup.sh`, …).

### F. Standalone C++ test binaries

Six `cet_make_exec` targets that link the front-end interfaces directly and talk to
the hardware **without a running otsdaq system**:
`DTCFrontEndInterface_TestMain`, `CFOFrontEndInterface_TestMain`,
`DTCFrontEndInterface_ExtCFOMain`, `DTCFrontEndInterface_HWEventBuilding`,
`DCS_test`, `otsdaq_import_tracker_test_stand`.

They take bare positional arguments (`<deviceIndex> <numberOfEventWindowMarkers>`).
This is the "expert, machine is down" path — a second, entirely separate mode of
operation from everything above.

---

## 4. What a client actually has to do

Putting A–D together, the minimum viable remote client is:

1. Resolve a base URL (on-site gateway `:8443`, or `localhost:3075` through the
   standard SSH tunnel) and an instance.
2. Authenticate — obtain a `CookieCode` (see §5.3).
3. `POST` to `/urn:xdaq-application:lid={LID}/Request?RequestType=…`.
4. Parse an **XML** response and dig out `<ROOT>/<DATA>`. Some payloads are JSON
   *inside* an XML attribute (`getPVSettings`, `getDAQState`) and need a second
   parse.

None of this needs anything exotic — `requests` + `xml.etree` covers it. There is no
websocket, no binary protocol, no xdaq SOAP required for the read/command paths we
care about.

---

## 5. Findings that should shape the design

### 5.1 The macro list must be discovered at runtime, not compiled in

`DTCFrontEndInterfaceImpl.cc:899-980` shows the DTC interface, at configure time,
enumerating its child ROCs and **re-registering every ROC macro on itself** as a
forwarding macro — named either `ROC FEMacro - {name}` (when all ROCs are the same
type) or `Link{N}_{rocName}_{name}` (when they differ). `RunROCFEMacro` then
dispatches via `rocFEMacroMap_`.

Consequences:

- The set of callable macros **depends on the active configuration**, not just on the
  source. A statically generated CLI would be wrong on any system whose ROC mix
  differs from whatever we generated against.
- Therefore: **`getFEMacroList` at runtime is the source of truth**, and the static
  inventory in `data/otsdaq-femacros.json` is documentation/validation input, not a
  command table.
- It also means the effective macro count on a live system is *larger* than 184.

### 5.2 Argument names are hostile to a command line

Registered argument names are human GUI labels, e.g.:

```
Target ROC (Default = -1 := all ROCs)
port (Default: -1, current active)
fpga [0,1,2,3]
Low Pulse Width (Clock Cycle := 10 ns)
```

They contain spaces, commas, colons, brackets and `=`. Since the wire format is
itself `name,value` pairs joined by `;`, a name containing a comma or semicolon is
ambiguous on the wire. Any CLI needs a **slugging scheme** (`--target-roc`) plus a
reverse map to the exact registered string, and must URL-encode aggressively. This is
the main source of fiddly work in the project.

Macro *names* have the same problem to a lesser degree (`"Do the CRV Fancy Dance"`,
`"CFO DTC Soft Reset"`).

### 5.3 Authentication is unresolved, and there is a checked-in credential

`otsdaq-mu2e-crv/UserWebGUI/js/mu2e.js:21` contains a **hardcoded 512-hex-character
`CookieCode`** committed to the repository, used to authenticate all LID 281
(configuration read/write) requests. Ten functions depend on it —
including `saveSpecificTable`, `saveNewTableGroup` and `activateTableGroup`, i.e.
configuration *writes*.

Two separate issues:

1. **Security.** A long-lived session credential in git, granting configuration-write
   access, is worth raising with the CRV group independently of this project. If it
   is still valid it should be revoked; if it is dead, it should be deleted so nobody
   copies the pattern. *This document does not assume either way.*
2. **Design.** We must not repeat it. The CLI needs a real login flow. The login
   endpoint lives in the otsdaq core (not in this repo), so **determining how to
   obtain a `CookieCode` programmatically is an open question and the single
   biggest unknown blocking a write-capable CLI.** Read-only paths through LID 200/302
   appear to work without one in `mu2e.js`, which suggests a useful first milestone.

Note also that per `mu2edaq-operations/shifter/docs/ots/access.md` referenced from the
ops docs, otsdaq has its own account system — reconciling that with the suite-wide SSO
preference is a separate conversation.

### 5.4 No prior art in the suite to reuse

I searched every `mu2edaq-*` package for otsdaq/xdaq clients. There is **no existing
Python client** — only documentation (`mu2edaq-operations/shifter/docs/ots/`) and a
setup shell script. `mu2e.js` (2310 lines) is the only working client of this API
anywhere in the tree, and it is browser JavaScript.

That makes `mu2e.js` the most valuable single artifact for this project: it is a
de-facto protocol specification. It is also the right thing to port, function by
function — its ~60 API functions map almost 1:1 onto what a Python client library
would need.

### 5.5 Responses are XML, inconsistently

`<ROOT><DATA>` with payload in attributes, sometimes containing embedded JSON
strings that need a second parse, sometimes with repeated elements that must collapse
to a list (`mu2e.js:xmlToJson` handles all three cases). Error reporting is not
uniform: `transition` signals failure via a `state_transition_attempted` attribute
rather than an HTTP status. **HTTP 200 does not mean the command succeeded.**

---

## 6. Scope assessment

The work divides cleanly into four tiers of increasing risk. I'd recommend committing
only to tier 1 up front.

**Tier 1 — client library + read-only tools.** *Low risk, high value.*
Port the transport from `mu2e.js`: URL/LID construction, POST, XML→dict, error
detection. Then read-only commands: `getCurrentState`, `getRunInfo`, `getDAQReport`,
`getFEMacroList`, `getPvData`, `GetConsoleMsgs`. No auth needed for most of this,
which means it can be built and tested before the `CookieCode` question is answered.
This alone gives us scriptable DAQ status — genuinely useful on its own.

**Tier 2 — FE macro invocation.** *Medium risk.*
Runtime discovery via `getFEMacroList`, argument slugging (§5.2), `runFEMacro`,
output parsing. The payoff is the whole 184+ macro surface becoming scriptable.
Risk is concentrated in argument-name handling and in not having a safe test target.

**Tier 3 — run control and configuration.** *High risk.*
State transitions and the LID 281 table/group/alias operations. Blocked on auth
(§5.3), and these are the operations that can disrupt a running experiment. Needs
explicit confirmation semantics and a dry-run mode.

**Tier 4 — wrapping the shell scripts (§E) and test binaries (§F).** *Separate project.*
Different execution model entirely (local, needs hardware, needs Vivado/spack). Worth
deliberately excluding from v1.

### What I'd want decided before writing code

1. **Read-only first, or go straight for macro execution?** (Tier 1 vs 1+2.)
2. **How do we authenticate?** Someone needs to find the otsdaq login endpoint in the
   core, or confirm we run tools with an operator-supplied cookie. This gates Tier 3
   entirely.
3. **Is there a test instance** we can point at that is not the production DAQ? Tier 2
   is hard to develop safely without one.
4. **Multi-instance addressing** (§C): does the CLI target one instance per
   invocation, or should it understand the shift/subsystem hierarchy natively?
5. **Should the C++ side of `mu2edaq-commandline-tools` get an otsdaq client too**, or
   is Python sufficient for this domain? The package supports both; the otsdaq work is
   naturally Python-shaped.

### Rough size

The client library is small — `mu2e.js`'s transport is ~60 lines and the whole file is
2310 lines of mostly DOM manipulation we don't need. I'd estimate the Python client
core at a few hundred lines, with the argument-mapping layer (§5.2) being the part
that actually takes thought. The 184-macro inventory is *data*, not code — it does not
scale the implementation.

---

## Appendix A: Complete FE macro inventory

184 active registrations. Full metadata (arguments, permissions, descriptions, source
locations) is in [`data/otsdaq-femacros.json`](../data/otsdaq-femacros.json).

### `otsdaq-mu2e` / `DTCFrontEndInterface` (52)

ROC Setup; ROC Write; ROC Read; ROC Firmware Inventory; List Firmware Directory; ROC
Block Read; ROC Block Write; Headers Format test; ROC_Write_ExtRegister;
ROC_Read_ExtRegister; Buffer Test; Pattern Test; DTC_HighRate_DCS_Check;
DTC_HighRate_DCS_Block_Check; DTC_SendHeartbeatAndDataRequest; DTC Instantiate; Buffer
Test Detached; DTC Write; DTC Read; Event Mode Required Mask Set; Event Mode Required
Mask Read; Loss-of-Lock Counter Read; Loss-of-Lock Counter Reset; Spy Buffer; Release
All Data DMA Buffers; Get DTC Counters; Get Link Lock Status; Configure DTC for
HWDevmode; Read Rx Diag FIFO; Read Tx Diag FIFO; Get Link Errors; Configure for Timing
Chain; Loopback CFO Emulator Test Run; Loopback CFO Emulator Multi Test Run; Loopback
Manual Setup; Enable/Disable DTC Link; Reset ALL (CFO/ROC/EVB) DTC Links; Reset CFO
Link Rx; Reset CFO Link Tx; Reset CFO Link Rx PLL; Reset CFO Link Tx PLL; Get DTC ID
and Hardware EVB Info; Set DTC ID and Hardware EVB Info; CFO Interface (Emulation)
Setup; CFO Emulator On/Off Spill Emulation Setup; CFO Emulator Fixed-width Event Window
Emulation Setup; DTC Software Data Request; DTC Punched Clock; Program ROCs; Validate
DTC Control Registers — plus the 2 registered under runtime-constructed names (§5.1).

### `otsdaq-mu2e` / `CFOFrontEndInterface` (26)

CFO Reset; Clock Marker Enable/Disable; CFO Halt; CFO Write; Loopback Test; CFO Read;
Reset Runplan; Compile Runplan; Set Runplan; Compile, Set, and Launch On/Off Spill
Template Run Plan; Compile, Set, and Launch Fixed-width Event Window Template Run Plan;
Launch Runplan; Get CFO Counters; Shared Run Plan Get Status; Shared Run Plan Start;
Shared Run Plan Stop; Shared Run Plan Join; Shared Run Plan Single-shot Join; Shared Run
Plan Leave; Configure for Timing Chain; Super Orchestration Start; Super Orchestration
End; Super Orchestration; Buffer Test Detached; Runplan Subrun Config Setup; Runplan
Subrun Config Read.

### `otsdaq-mu2e` / `CFOandDTCCoreVInterface` (11)

CFO DTC Soft Reset; CFO DTC Hard Reset; Get Firmware Version; Flash LEDs; Get Status;
Get Simple Status; Check Firefly Temperature; Check Firefly Loss-of-Light; Check FPGA
Temperature; Jitter Attenuator Setup; Get Device Index.

### `otsdaq-mu2e` / `CAPTANSignalGenerator` (7)

Reset; Get Firmware Version; Get Pulse Period; Get Manual Mode; Set Manual Mode; Set
Burst Mode; Set Pulse Period.

### `otsdaq-mu2e` / `ROCPolarFireCoreInterface` (5)

Setup for Pattern Data Taking; Read SPI Flash Block; Write SPI Flash Directory; Erase
SPI Flash Block; Force Clear Action Lock.

### `otsdaq-mu2e` / `ROCCoreVInterface` (2)

Get ROC Status; Get ROC Firmware Version.

### `otsdaq-mu2e-crv` / `ROCCosmicRayVetoInterface` (42)

Do the CRV Dance; Do the CRV Fancy Dance; Get Firmware Version; Get Test Counter; Set
Test Counter; Reset uC; Set Input Mask; Configure CRV (FEBI); Configure ROC; FEB
Configure; Soft Reset; Get Status; Get Status Pretty; Get POOL; FEB Get Status Pretty;
FEB Take Pedestral; Read Fiber Rx; Read Fiber Tx; Set Loopback Mode; FEB Set Bias; FEB
Set Bias Trim; FEB Set Threshold; FEBs Set Pipeline Delay; FEBs CMBENA; PWRRST;
Histogram; Register Dump; FEB II Set Threshold; FEB II Set Bias; FEB II Set Bias Trim;
FEB II Set Gate OnSpill; FEB II Set Gate OffSpill; FEB II Set Channel; FEB II Get
Status; Test FEB Connection; Test ROC Links; FEB II Set AFE Offset; FEB II Baselines;
FEB II Trigger Baselines; FEB II Configure; FEB II Configure from Tables; FEB II Reset
and Align.

### `otsdaq-mu2e-calorimeter` / `ROCCalorimeterInterface` (25)

Setup for Fixed-length Pattern Data Taking; Send Mz Command; Enable and Power SiPMs;
Enable/Disable MZB Leds; Find BoardID From Serial; Set Board Voltages; Configure Link;
Calibrate Mzb; SetADCsThresholds; ReadVoltagesFromDB; ReadChannelStatusFromDB; Print ROC
Configuration; SetupForNoiseTaking; Read ROC Error Counter; Setup for ADCs Data Taking;
Toggle MB Busy for Noise; ROC Status; MZB Status; ROC Slow Control; TRAD Slow Control;
TRAD Set Mask; Read MB Registers; Evaluate BlockWrite Error Rate; Configure State
Machine; Create Global ROC Table.

### `otsdaq-mu2e-sync` / `ROCMobileSyncInterface` (9)

Configure State Machine; Read Histograms; Reset; Setup For Run; Selective Reset; Reset
Histograms; Read Rx FIFO; Read Tx FIFO; BERT Setup.

### `otsdaq-mu2e-tracker` / `ROCTrackerInterface` (5)

Read Register; Reset Counters; Find Alignment; Set Threshold; Measure Threshold.

---

## Appendix B: How this survey was done

- FE macros: `tools/extract-femacros.py` parses `registerFEMacroFunction(...)` call
  sites with a brace-matching scanner (the calls span many lines and are heavily
  comment-interleaved). It distinguishes active from `//`- and `/* */`-commented
  registrations. Re-run it after any otsdaq-mu2e update to refresh
  `data/otsdaq-femacros.json`.
- Protocol: read from `otsdaq-mu2e-crv/UserWebGUI/js/mu2e.js` and the calorimeter
  HTML pages, cross-checked against `RequestType=` occurrences across all
  `UserWebGUI` trees.
- Operational topology: `mu2edaq-operations/shifter/docs/ots/`.

**Caveats.** The otsdaq core is not in this repo, so the endpoint list is only what
Mu2e code calls — the real API is larger. Nothing here was verified against a live
otsdaq instance; it is all read from source. The two runtime-named macro families
(§5.1) mean the live macro count exceeds the static count.
