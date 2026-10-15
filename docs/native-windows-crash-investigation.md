# Block E — unresolved Windows native crash investigation

The Block D `0xC0000005` remains an **unresolved reliability issue**. A bounded CPU-only investigation did not reproduce it. No environment repair or runtime change was made, and neither the earlier passing rerun nor this investigation establishes a fix.

## What the preserved evidence establishes

The original command was `.venv\Scripts\python.exe -B -m pytest -q -W error`. Its receipt places the run between **2026-10-15 13:48:27.326802 and 13:48:47.443301 UTC**, with exit `3221225477` (`0xC0000005`). The original traceback and receipts remain in `var/mission06-offline/block-d-validation-20261015-224752-f4e5f3/`; see the [Block D report](reports/winning-quality-block-d.md).

The Python stack records `pydantic.main.BaseModel.__init__` while [the planner](../backend/src/rekit/recovery/planner.py) constructs a `RecoveryAction` for **RETAIN**. Its caller was the normal branch of the zero-time sensitivity test's wrapper (`bounded_solve`, line 103), inside `analyze`. Candidate generation precedes creation of that call's CP-SAT model/solver. The failing labor rate was not retained. The stack therefore does **not** show that the deliberate zero-time solve was executing, or establish that CP-SAT caused the fault.

A read-only Application Event Log query found exactly one `python.exe` event ID **1000**, provider **Application Error**, in 13:46–13:51 UTC:

| Retained field | Recorded value |
| --- | --- |
| Event time | `2026-10-15T13:48:42.8207286Z` |
| Fault module | `_pydantic_core.cp312-win_amd64.pyd` |
| Exception | `c0000005` |
| Fault offset | `000000000001253c` |
| Application version | `3.12.10150.1013` |
| Module file version | `0.0.0.0` — not the Python package version |
| Process ID | `0x96c4` |

The event lies inside the original attempt's interval and agrees with the Python frame's module attribution. The original command receipt did not retain its PID, so exact PID correlation cannot independently be proved. No raw event message, unrelated event, account identifier, user directory, or process dump was retained. The OS's faulting-module attribution identifies the observed fault site; it does **not** distinguish a defect there from memory corrupted earlier elsewhere.

Microsoft describes `0xC0000005` as an invalid memory access and lists several possible causes. The exception code alone is not a diagnosis. [Microsoft access-violation documentation](https://learn.microsoft.com/en-us/shows/inside/access-violation-c0000005-read-or-write).

## Environment and bounded investigation

Investigation source checkpoint: `258b169f952bc5cfe1bd71e0ed1a0c1b7867fafd`, plus the new diagnostic harness. The inspected `.venv` has CPython **3.12.10**, Windows **11 / 10.0.26300**, AMD64 / 64-bit; Pydantic **2.14.1**, pydantic-core **2.50.1**, OR-Tools **9.15.6755**, protobuf **6.33.6**, NumPy **2.5.2**, pandas **3.0.6**, pytest **9.1.1**. These are observations of the existing installation, not a compatibility certification or a reason to upgrade it. Package and relevant native-binary hashes are in the environment receipt. No torch import, GPU inference, dependency installation, environment-variable change, credential access, authenticated network request, or AMD attempt was performed.

The new [diagnostic harness](../evaluation/investigate_native_crash.py) uses only the accepted synthetic canonical case. It verifies the frozen receipt SHA-256 `c405c532543cfbba0d32632025e0272a1f79c0bcdc88cc402ed9e4138ab507e7`, its fixture hashes, and problem fingerprint before workloads. Each experiment runs in a fresh Python subprocess; the two concurrency experiments explicitly share no solver objects. `solve_recovery` already constructs a fresh model/solver per call, with **one search worker**, seed **0**, and a **10-second** normal solver limit. Deliberate zero-time calls retain the existing `UNKNOWN`/no-allocation behavior. This investigation introduces no production concurrency or process boundary.

The harness adds `-X faulthandler` to diagnostic children and uses `-B`. This is a recorded difference from the original CLI, not an environment change. Python documents its Windows exception handler and Python-stack output; these logs do not substitute for a native memory dump, symbols, registers, or a root-cause trace. [Python 3.12 faulthandler documentation](https://docs.python.org/3.12/library/faulthandler.html).

Each child has at most **120 seconds**, and the whole matrix has a **480-second** deadline. Any failed child, native crash, or timeout stops subsequent stress work; a failed concurrency child stops its owned peer. Logs and return codes are retained. The output directory must be new and inside ignored `var/mission06-offline`; existing evidence cannot be overwritten. Pytest fixtures use temporary application stores; the separate diagnostic workers only read the frozen snapshot and construct in-memory models. No persistent application inventory or evidence store is changed.

| Experiment, in execution order | Bound and purpose | Actual result |
| --- | --- | --- |
| Environment observation | Allowlisted versions, interpreter and installed native-file hashes; no environment dump | Passed, 0.469 s |
| Exact formerly failing test | Three fresh processes, same node, `-q -W error`; does not repeat the full suite | 1 passed each; processes 2.015 / 1.875 / 1.891 s |
| Collection and preceding test context | Collect nodes; run the prefix through the failing test in collected order, maximum 400 nodes | 1,500 nodes collected; **212 passed in 19.06 s**; prefix process 19.547 s |
| Action validation without solving | 1,000 batches ×19 frozen candidate payloads; alternate constructor and `model_validate`; validate equality | **19,000 validations**, no CP-SAT solves; 0.594 s |
| Sequential solver lifecycle | Three complete 201-rate sweeps in one process; third forces only rate 170 to zero time | **603 solves**; first two fully verified; third correctly withholds its frontier with `UNKNOWN` at 170; 1.875 s |
| Python-thread variation | Two threads ×25 solves, independent input models and solver per call, one zero-time call per thread | **48 OPTIMAL +2 UNKNOWN**, expected values and unchanged inputs; 0.594 s |
| Process-isolation variation | Two concurrently spawned Python interpreters ×25 solves, same workload as each thread | Each **24 OPTIMAL +1 UNKNOWN**; each process 0.609 s |

This is a small diagnostic matrix, not a load benchmark, a soak test, or evidence of production thread safety. Worker timing includes interpreter startup; it is not a performance claim. Only the thread variant deliberately adds Python-thread concurrency. The original pytest invocation had no parallel-execution flag; no evidence currently identifies multiprocessing as its cause. The process variant uses separate interpreter processes, not shared solver serialization or a forked native context.

The full matrix ran **2026-10-15 14:38:03.855212–14:38:34.686008 UTC**, **30.828 seconds**, without timeout or native failure. Harness/source hashes and the four protected prior-evidence hashes matched before and after. The exact collection order and all actual subprocess argument arrays are recorded in the receipt. The five new [harness safety tests](../tests/backend/test_native_crash_investigation.py) passed separately in **0.20 seconds**; they test evidence preservation, native-error retention, owned-child timeout handling, deadline refusal, and stop-on-first-failure with simulated child processes, not additional native stress.

OR-Tools defines `UNKNOWN` as an unproved result when search stops before reaching another status; it must remain distinct from `OPTIMAL`. Passing the diagnostic means the zero-time result remained visibly unverified, not that an optimum was claimed for that call. [Google CP-SAT documentation](https://developers.google.com/optimization/cp/cp_solver).

## Hypotheses and negative findings

| Possibility | Evidence for considering it | What remains unproved |
| --- | --- | --- |
| Fault within native validation or its input/lifetime state | Both the OS event and Python stack point to pydantic-core during `RecoveryAction` construction | No malformed payload, library defect, ownership error, or minimum reproducer identified; 19,000 controlled validations passed |
| Earlier native memory corruption or object-lifetime interaction, possibly after prior solver calls | The original same-process test context included many previous calls; the faulting frame alone cannot locate the initiating write | Three sequential sweeps and the preceding 212-test context passed; no evidence specifically assigns corruption to OR-Tools or another extension |
| Timing, threading, or process interaction | Native scheduling can differ across executions; neither original receipt nor Python stack is a native-thread history | Separate-solver thread/process variations passed; they do not exhaust interleavings or prove a safer production architecture |
| Zero-time solver lifecycle | The failing test intentionally exercises a zero-time call somewhere in its sweep | The saved frame is the normal branch before its current solver is created; all controlled zero-time calls returned the expected unverified result |
| OS, hardware, or unrelated native dependency problem | Such causes cannot be excluded by the exception code | No diagnostic evidence establishes them; no hardware stress, dump configuration, privileged inspection, or unrelated event collection was performed |

The direct validation fault site has the strongest observational support. All causal explanations remain hypotheses; the matrix does not justify ranking one library as the culprit. The earlier Block D isolated pass and full **1,500-test** passing rerun remain historical observations. A test-name-only wording change between those runs was not a behavioral fix. This investigation did not upgrade packages, tune garbage collection, change CPU/GPU settings, alter the optimizer, loosen domain validation, or hide a failing test.

## Reproduction commands and receipts

From the repository root, the executed coordinator command was:

```powershell
.venv\Scripts\python.exe -B -X faulthandler evaluation/investigate_native_crash.py --output var/mission06-offline/block-e-native-investigation-20261015-first
```

Do not reuse that existing output directory. A future explicitly scheduled investigation requires a new path and the same bounded coordinator. The receipt contains every exact child command, including all 212 prefix node IDs; the internal `--worker` switches are not the recommended entry point because the coordinator supplies subprocess deadlines.

The separate safety-test command was:

```powershell
.venv\Scripts\python.exe -B -m pytest -q -W error tests/backend/test_native_crash_investigation.py
```

All detailed logs are retained locally under `var/mission06-offline/block-e-native-investigation-20261015-first/`. They are ignored execution evidence, not submission assets or evidence of independent human review. Selected SHA-256 anchors:

| Artifact | SHA-256 |
| --- | --- |
| Original Block D fatal traceback | `08c2467100fa09dac82636427a9540ec62caec0f009f39aca12b1239237e74c3` |
| New matrix `receipt.json` | `f357c5a174c4b1eb671bd9689665aff61b7802ed874b800ff17ae18a78750a2c` |
| `windows-event-sanitized.json` | `b64196b77adf61ee7bcb46f8f45330a6e9db6c3e8cc3ce872658a33dd068ec26` |
| Harness as executed | `26f3103a54e197303373406ac339fed3710cca3e9a8df847e05108ffd601a2db` |

The sanitized event receipt also records the query window and correlation limits. The read-only query was `Get-WinEvent -FilterHashtable @{LogName='Application'; StartTime=<13:46 UTC converted to local>; EndTime=<13:51 UTC converted to local>; Id=1000}`; only matching `python.exe` fields listed above were retained.

## Residual risk and next action

The root cause and recurrence rate are unknown. Three repeats and one preceding-test context cannot rule out an intermittent native fault. Current passing validation supports continuing bounded offline preparation; it does not establish unattended operational reliability or resolve Mission 06's independent AMD blocker.

On any recurrence, stop further stress immediately, retain the first failing process's output, exact command, input and source hashes, version/native-binary metadata, UTC interval and exit code, and compare the Application Error module/time. Do not automatically retry until it passes. A useful subsequent investigation would need a reproducible case or an owner-approved native debugging/dump plan with storage and privacy controls; no dump collection, debugger setup, privileged changes, dependency changes, paid resources, or production isolation change is authorized by this report. Any suspected upstream defect should be reported only after a minimized sanitized reproducer and owner authorization to contact its maintainers.
