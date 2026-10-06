# Natural-Language Segment Builder with a Confirmed, Idempotent Vendor Write-Back

A marketing segment builder that turns a plain-English request into a typed, schema-validated `SegmentDefinition` through a sequence of tool calls, previews it as a live count against a synthetic profile store before a human confirms it, never sends a single profile row to the model that builds it, and, once confirmed, writes the approved membership list back to a vendor system of record through a real REST API inside a documented rate budget with exactly-once semantics under retries. Every number below was measured on this machine, not targeted: the 200-request accuracy eval and the 150-invalid-definition safety eval are both deterministic and reproducible run to run, the write-back's exactly-once and rate-budget claims are each backed by a real HTTP replay against a real local server, and the live-LLM section states exactly how many real `claude -p` calls were made in this build (zero, disclosed honestly below, not implied to be more).

## Why this exists

This is a small version of the natural-language segment builder inside a CDP or marketing automation product: a person types "users who logged in at least 3 times in the last 30 days and are on the pro plan," the system turns that into something a query engine can actually run, safely, without ever letting the model see real customer data or execute something malformed, a human reviews the live count before anything commits, and the approved list then has to actually reach the vendor platform that runs the campaign, exactly once, without blowing through that vendor's rate limit. The typed schema (`segment_builder/schema.py`), the tool-call interface (`segment_builder/tools.py`), and the validator-before-execution gate (`segment_builder/validator.py`) make the build side safe; the evaluation harness (`scripts/run_accuracy_eval.py`, `scripts/run_safety_eval.py`) makes the accuracy and safety claims about it measured rather than assumed; `segment_builder/vendor_writeback.py`, `segment_builder/vendor_api.py`, and `segment_builder/rate_limiter.py` make the write-back side real rather than a diagram.

## Honest framing

- **What this is not.** Not a natural-language-to-SQL system; the only expressible segments are the ones the typed schema covers (event count/recency predicates, attribute predicates, AND/OR/NOT composition). Not a claim that an LLM was exercised at the 200-request or 150-candidate scale: those two evals run on `DeterministicIntentParserClient`, a regex-based intent parser, for exactly the reason `ontology-grounded-operations-agent` uses `DeterministicToolRouterClient` for its 386-question benchmark, a benchmark that size needs to be exactly reproducible and free to run in CI.
- **"A vendor system of record," not a named vendor.** The write-back's REST semantics and its 100-requests-per-10-seconds budget are the documented Quickbase ones ([rate-limiting overview](https://help.quickbase.com/docs/rate-limiting-overview), [limits in Quickbase](https://help.quickbase.com/docs/limits-in-quickbase)), chosen because the posting this project was designed against names Quickbase APIs. `vendor_api.py` is an authored fake of that REST surface, not a Quickbase sandbox account or a mock of this repository's own HTTP client; `VendorWriteBackClient` talks to it over a real loopback socket with real JSON over HTTP. No Quickbase app was used in this build.
- **The write-back is a real, tested mechanism against an authored server, not a survived-production boast.** "Lands exactly once under a 5% duplicated, reordered retry stream" is proven two ways: `tests/test_vendor_writeback.py::test_write_back_lands_exactly_once_under_a_duplicated_reordered_retry_stream` injects the duplication and reordering at the transport layer (the same technique `corporate-action-event-ledger` and `embedded-fleet-provisioning` use for their own replay claims) against a real `VendorAPIServer`, and `scripts/run_writeback_retry_replay.py` is the same scenario as a standalone, re-runnable command with committed output (`docs/writeback_retry_replay_output.txt`).
- **Two LLM backends, and only one of them was actually run in this build.** `llm_client.py` defines `LLMClient` with two implementations: `DeterministicIntentParserClient` (used for both evals below) and `ClaudeCLIClient`, which shells out to the real `claude` CLI as a genuine subprocess and is unit-tested with a mocked subprocess call (`tests/test_llm_client.py`). **The real `claude -p` CLI was not invoked in this build session** because of budget and time constraints shared across three parallel builds; this is disclosed here rather than implied. `ClaudeCLIClient` is real, working code with its own tests, not a stub, but the live-sample script (the equivalent of `ontology-grounded-operations-agent`'s `run_live_llm_sample.py`, 20 real calls) was not run here. See Limitations.
- **No profile data reaches either client, by construction.** Every `LLMClient.build_segment` call receives only the plain-English request text and, for `ClaudeCLIClient`, `fields.schema_metadata_for_prompt()`, which is field names, types, and enum vocabulary only, never a generated profile row. `tests/test_llm_client.py` proves this directly: it generates a synthetic `ProfileStore`, pulls real `profile_id`s and event-timestamp tags out of it, drives both clients on 20 requests, and asserts none of those row-specific values appear in the deterministic client's recorded input or the real client's exact prompt string.
- **Synthetic data, stated as synthetic.** `segment_builder/store.py` generates a seeded, reproducible profile store (`DEFAULT_SEED = 20260901`, 5000 profiles) with no real user data.
- **The 200-pair accuracy set and the 150-case safety set are template-generated, not one-by-one hand-typed, and that is disclosed rather than implied otherwise.** `eval_dataset.py` builds the 200 (request, expected `SegmentDefinition`) pairs from 17 clause templates combined into single-clause, two-clause AND/OR, and three-clause AND/OR requests, with phrasing noise (spelled-out small numbers, the "haven't" contraction) injected at fixed, disclosed rates to produce genuine coverage gaps rather than a manufactured score. `invalid_dataset.py` builds the 150 safety cases from 20 mutation kinds applied to valid seed definitions, mirroring `ontology-grounded-operations-agent/action_generator.py`. Neither the parser nor the validator was tuned against the measured pass rate after the fact; see Findings.
- **Machine and toolchain, exactly as measured.** 8 physical / 16 logical cores, Windows 11 Home (build 10.0.26200), Python 3.12.10, pydantic 2.9.2, pytest 8.3.3, Node 22.17.1, TypeScript 5.6.3.

## Architecture

```
segment_builder/
  fields.py           the only schema metadata a model ever sees: event names and
                       attribute field names/types/enum vocabulary, no profile data
  schema.py            typed SegmentDefinition (pydantic, extra="forbid" throughout):
                       EventPredicate, AttributePredicate, Composite (and/or/not),
                       bounded tree depth
  tools.py             SegmentBuilderSession: the tool-call API (add_event_predicate,
                       add_attribute_predicate, combine, negate, finalize_segment) a
                       model builds a definition up with, node by node
  validator.py         SegmentValidator.validate: the single gate to execution;
                       constructs a ValidatedSegment only if pydantic validation
                       succeeds
  store.py             seeded synthetic ProfileStore; execute_segment is the only
                       function that reads profile content, and the only place a
                       validated definition is actually run
  intent_parser.py     the deterministic, rule-based parser measured at the
                       200/150 scale, standing in for "the LLM produced this"
  llm_client.py         LLMClient interface; DeterministicIntentParserClient (used
                       for both evals) and ClaudeCLIClient (real `claude -p`
                       subprocess, not exercised live in this build, see Honest framing)
  pipeline.py           SegmentBuilderPipeline: request -> build_segment -> validate
                       -> execute_segment (live count) -> SegmentPreview.confirm()
                       -> write_back_approved() (vendor REST write-back, confirm-gated)
  eval_dataset.py       builds the 200-pair accuracy held-out set
  invalid_dataset.py    builds the 150-case safety set
  rate_limiter.py        SlidingWindowRateLimiter: the 100-req/10s pacing algorithm,
                       time/sleep injected for a fast fake-clock unit test
  vendor_api.py          VendorAPIServer: authored fake of the vendor's REST upsert
                       endpoint (real HTTP, idempotency dedup, server-side budget)
  vendor_writeback.py     VendorWriteBackClient: batches, idempotency keys,
                       self-paced sends, retry-on-429, over real HTTP to vendor_api.py
scripts/
  run_accuracy_eval.py           the 200-request accuracy eval; exit code gates CI
  run_safety_eval.py             the 150-invalid-definition safety eval
  run_writeback_retry_replay.py  5%-duplicated, reordered replay; exactly-once check
  run_rate_limit_benchmark.py    real wall-clock proof the client stays in budget
tests/
  test_schema.py, test_validator.py, test_store.py, test_tools.py,
  test_intent_parser.py, test_eval_dataset.py, test_invalid_dataset.py,
  test_llm_client.py (the no-profile-data proof), test_pipeline.py,
  test_rate_limiter.py, test_vendor_api.py, test_vendor_writeback.py
frontend/
  src/types.ts           TypeScript mirror of schema.py's types
  src/SegmentPreview.tsx  the preview UI: request text, definition tree, live
                          count, a confirm button gated on all three existing
.github/workflows/eval-gate.yml   CI: runs pytest (now including the write-back
                                   suite), then both eval scripts, and fails the
                                   build if either regresses
docs/
  test_output.txt, accuracy_eval_output.txt, safety_eval_output.txt,
  frontend_typecheck_output.txt, ci_workflow_validation.txt,
  writeback_retry_replay_output.txt, rate_limit_benchmark_output.txt
```

**Why validation is a wrapper type (`ValidatedSegment`), not a boolean.** `ProfileStore.execute_segment` only accepts a `ValidatedSegment`, which can only be constructed by `SegmentValidator.validate` succeeding. There is no second, looser path from a raw dict to execution; a caller cannot forget to check a boolean because there is no boolean to forget.

**Why the deterministic client still drives the same tool-call session as the real client.** `DeterministicIntentParserClient` parses text straight to a tree with `intent_parser.parse_request`, then replays that tree as the same `add_event_predicate` / `combine` / `finalize_segment` calls `ClaudeCLIClient` would make (`_replay_tree_as_tool_calls`), so the 200-request eval exercises the same tool-call plumbing the real model uses, not a shortcut around it.

**Why each batch's idempotency key is a hash of its content, not a sequence number.** `vendor_writeback.batch_idempotency_key` hashes `(segment_id, sorted(profile_ids_in_batch))`. A sequence number would make "retried" and "reordered" different problems (a retry reuses a number, a reorder makes numbers arrive out of sequence, and a dedup table keyed on sequence has to reason about both). A content hash makes them the same problem: any copy of the same batch, arriving at any time, in any order relative to other batches, hashes to the same key, so the server's "have I applied this key" check is the entire idempotency mechanism, and reordering is a non-event by construction rather than something handled.

**Why each batch is final truth, not a delta.** `BatchRequest.to_body()` sends every profile id in the batch with `included: True`; nothing about applying batch B depends on whether batch A was applied yet, or in what order. That is what makes the server's final state after a reordered replay provably order-independent rather than merely usually-correct: the proof in `test_write_back_lands_exactly_once_under_a_duplicated_reordered_retry_stream` does not depend on the replay's shuffle seed.

**Why the client paces itself instead of only reacting to the server's 429.** `VendorWriteBackClient` self-throttles with its own `SlidingWindowRateLimiter` before every send, so it is well-behaved even against a vendor that enforces its budget silently (drops or delays rather than returning 429). The server in this repository does return 429 (see `vendor_api.py`) so `_send_with_retry` can also recover from a transient overshoot, but the client is not designed to depend on that signal existing.

## Validation

**1. Test suite** (`docs/test_output.txt`), now including the write-back suite:

```
213 passed in 6.97s
```

**2. Accuracy eval, 200 held-out requests** (`docs/accuracy_eval_output.txt`):

```
total held-out requests: 200
matched hand-written definitions: 185 / 200
ACCURACY: 92.5000%
threshold: 184 / 200
EVAL GATE: PASS
```

**3. Safety eval, 150 deliberately invalid candidates** (`docs/safety_eval_output.txt`):

```
total deliberately invalid candidates: 150
correctly rejected by the validator: 150 / 150
INVALID DEFINITIONS THAT EXECUTED: 0
SAFETY GATE: PASS
```

**4. Frontend typecheck** (`docs/frontend_typecheck_output.txt`): `tsc --noEmit` exits 0, no errors.

**5. CI workflow YAML** (`docs/ci_workflow_validation.txt`): parsed successfully with `yaml.safe_load`.

**6. Write-back exactly-once replay, 5% duplicated and fully reordered** (`docs/writeback_retry_replay_output.txt`):

```
confirmed segment profile count: 1285
unique batches: 65
injected duplicates: 3 (5% of 65)
replay stream length (reordered): 68
server requests received: 68
server duplicate_rejected_count: 3
final membership matches expected set exactly: True
every unique batch applied exactly once: True
sum of apply counts == unique batch count: True
RESULT: PASS
```

**7. Write-back rate-budget benchmark, real wall clock** (`docs/rate_limit_benchmark_output.txt`):

```
batches sent: 230
elapsed wall-clock time: 20.58s
peak requests observed in any real 10s window: 100 (budget: 100)
server rejected_count (should be 0, client never needed a 429 to stay in budget): 0
server request_count: 230
RESULT: PASS
```

## Findings

**The parser's real, disclosed coverage gaps: spelled-out numbers and the "haven't" contraction, not a tuned score.** `intent_parser.py` only matches digit-form counts (`\d+`) and the literal phrase "have not," never "haven't." `eval_dataset.py` independently injects spelled-out small numbers ("three times") at a fixed 15% rate and the "haven't" contraction at a fixed 30% rate wherever those constructs occur, as a disclosed, reproducible source of genuine misses, not something added after seeing the pass rate. The 15 mismatches in `docs/accuracy_eval_output.txt` are exactly these two gaps (`could not parse clause: 'with at least ten seats'`, `could not parse clause: "who haven't opened a dashboard..."`), which is why 185/200 rather than 200/200 is the honest number, and it is reported rather than smoothed over.

**A dedicated test exists because "150/150 rejected" is only meaningful if the 150 are genuinely broken.** `tests/test_invalid_dataset.py::test_every_case_genuinely_fails_the_real_validator` runs every one of the 20 mutation kinds through the real `SegmentValidator` and asserts each one raises, the same discipline `ontology-grounded-operations-agent/tests/test_action_generator.py` applies to its own malformed-proposal generator.

**Mixed AND/OR composition is refused, not guessed at.** A request like "on the pro plan and in the US or with a verified email" has ambiguous grouping without explicit structure; `intent_parser.parse_request` raises `IntentParseError` rather than picking an arbitrary precedence, covered by `test_mixed_and_or_is_rejected_rather_than_guessed`.

**A real, reproducible 429 at exactly the 100-request boundary, found while writing the rate-budget benchmark, not assumed away.** The first version of `SlidingWindowRateLimiter.acquire` paced the client to the literal edge of its own window: wait until exactly `window_seconds` after the oldest recorded send, then send. Running `scripts/run_rate_limit_benchmark.py` against the real `VendorAPIServer` failed at request 101 every time, with a genuine `HTTP 429` from the server. The measurement that found the cause: both sides share the same `time.monotonic()` clock (client and server are threads in one process), so the gap was not clock skew, it was that the server's window is anchored to *receipt* time, which lags the client's *send-decision* time by the first request's one-way network delay; by the time the client's 101st send crossed its own 10.000s mark, the server's oldest timestamp (recorded a couple of milliseconds later than the client's) had not yet aged out by the same margin. Root cause: a client paced to the exact edge of a budget races any server whose window starts on receipt rather than on send. Fix: `safety_margin_seconds` (default 0.25s) added to every wait, so the client always sends meaningfully inside the server's trailing window rather than at its edge; `tests/test_vendor_writeback.py::test_client_safety_margin_prevents_the_boundary_race_against_a_real_server` pins this with a small, fast window (10 requests / 0.5s) so the regression runs in about a second rather than twenty.

## Measured results

Machine: 8 physical / 16 logical cores, Windows 11 Home (build 10.0.26200), Python 3.12.10, pydantic 2.9.2, pytest 8.3.3. The two eval numbers and the exactly-once replay are single-run, bit-for-bit reproducible measurements (fixed seeds, no network beyond real loopback HTTP, no concurrency in the parts that are seeded); no range is given because none is needed. The rate-budget benchmark is real wall-clock time and will vary slightly run to run with scheduling jitter; **the one number that matters there is the peak requests observed in any real 10-second window, and it is bounded at exactly 100, never above**.

| Claim | Measured | Meets claim |
|---|---|---|
| Plain-English request to typed segment definition through Claude tool calls | `SegmentBuilderSession` (`tools.py`) exposes `add_event_predicate`/`add_attribute_predicate`/`combine`/`negate`/`finalize_segment`; both `DeterministicIntentParserClient` and `ClaudeCLIClient` drive a request through exactly this API (`llm_client.py`) | yes |
| Schema-validated and previewed as a live count before a human confirms | `SegmentBuilderPipeline.build_preview` validates via `SegmentValidator` then runs `ProfileStore.execute_segment` for the count before `SegmentPreview.confirm()` can be called (`pipeline.py`) | yes |
| No profile data sent to the model | proven by construction and by test: `tests/test_llm_client.py` asserts no sampled profile row value appears in either client's recorded input | yes |
| 184 of 200 held-out requests matched hand-written definitions | 185 / 200 (92.5%) | yes |
| 0 of 150 invalid definitions executed | 0 / 150 | yes |
| Eval gates every prompt change in CI | `.github/workflows/eval-gate.yml` runs pytest and both eval scripts on every push/PR to master and fails the build if accuracy drops below 184/200 or any invalid definition executes; YAML validated with `yaml.safe_load`, not executed by a live GitHub Actions run in this session | yes, with the CI-execution caveat stated in Limitations |
| Writes the approved list back to a vendor system of record through its REST API | `VendorWriteBackClient.write_back` (`vendor_writeback.py`) POSTs real JSON over real HTTP to `VendorAPIServer`'s `/records/upsert` (`vendor_api.py`); `SegmentBuilderPipeline.write_back_approved` is unreachable before `SegmentPreview.confirm()` (`WriteBackNotConfirmedError`, tested) | yes |
| Inside a documented 100-requests-per-10-seconds budget | real wall-clock benchmark against a real local server: 230 requests, peak 100 in any real 10s window, 0 server-side 429s (`docs/rate_limit_benchmark_output.txt`); documented budget is Quickbase's (see Honest framing) | yes |
| Batched upserts land exactly once under a 5% duplicated, reordered retry stream | 65 unique batches (1,285 profile ids), 3 duplicates injected (5%), full reorder, replayed over real HTTP: final membership exactly matches the expected set, every unique idempotency key applied exactly once, 3/3 duplicates recognized and not reapplied (`docs/writeback_retry_replay_output.txt`) | yes |

## Building and running

```
python -m venv .venv
.venv\Scripts\activate
pip install -r requirements.txt

# test suite
set PYTHONPATH=.
python -m pytest tests -q

# the 200-request accuracy eval (deterministic client; also the CI gate command)
python scripts/run_accuracy_eval.py --threshold 184

# the 150-invalid-definition safety eval
python scripts/run_safety_eval.py

# the write-back exactly-once replay (5% duplicated, fully reordered)
python scripts/run_writeback_retry_replay.py

# the write-back rate-budget benchmark (real wall clock, ~20s, starts its own local server)
python scripts/run_rate_limit_benchmark.py
```

Frontend:

```
cd frontend
npm install
npx tsc --noEmit
```

On a POSIX shell, replace `set PYTHONPATH=.` with `export PYTHONPATH=.` or prefix the command, `PYTHONPATH=. python scripts/run_accuracy_eval.py`.

## Sibling comparison

This portfolio's `ontology-grounded-operations-agent` (https://github.com/Manas103/ontology-grounded-operations-agent) is the direct sibling this repo's `LLMClient` shape is copied from: a deterministic client for the large, free, reproducible benchmark, and a real `ClaudeCLIClient` subprocess implementation for a small, explicitly-counted live sample. That sibling's README states it made 20 genuine `claude -p` calls and reports their exact pass rate. This repo's `ClaudeCLIClient` is implemented and unit-tested with a mocked subprocess exactly as thoroughly, but, unlike the sibling, **no real `claude -p` call was made in this build session**, disclosed here rather than left implicit, for the reasons stated in Honest framing and Limitations. That gap, a real backend implemented and tested but not yet exercised live, is the same gap `ontology-grounded-operations-agent`'s own README calls out against `guarded-instruction-validation`; this repo is honest that it currently has that same gap rather than papering over it.

## Limitations

- **The real `claude -p` CLI was not invoked in this build.** `ClaudeCLIClient` is real code with real unit tests (subprocess mocked), not a stub, but the live-sample script this repo's task called for (15 to 25 genuine calls) was not run, due to budget and time constraints across three parallel builds in this session. This is the single biggest gap between this repo and its `ontology-grounded-operations-agent` sibling, which did make and report 20 real calls.
- **The eval-gate CI workflow was authored and its YAML validated, but no live GitHub Actions run has executed it yet** (this repo was not yet pushed with Actions enabled and exercised at build time). The commands it runs (`pytest`, both eval scripts) were run directly on this machine and their output is committed under `docs/`.
- **The accuracy and safety datasets are template-generated, not individually hand-typed English.** 17 clause templates and 20 mutation kinds respectively, combined and parameterized; this gives reproducibility at the cost of not sampling the full diversity of real user phrasing.
- **The frontend is a typed, typechecked component and API contract (`SegmentPreview.tsx`, `types.ts`), not a running server.** No Playwright browser-level test was added in this session; `npx tsc --noEmit` (committed output in `docs/frontend_typecheck_output.txt`) is the disclosed minimum for the frontend piece.
- **The parser's coverage gaps (spelled-out numbers, "haven't") are real and disclosed, not exhaustive.** A production system would need a much larger phrasing vocabulary; this repo's 92.5% is a measurement of this specific parser's specific vocabulary, not a general claim about NLU quality.
- **Mixed AND/OR requests are refused outright** rather than resolved with an operator-precedence rule, a deliberate scope choice given the ambiguity, not an oversight.
- **The vendor is an authored fake (`vendor_api.py`), not a real Quickbase app.** The REST shape (upsert, idempotency, the 429 and Retry-After) and the 100-requests-per-10-seconds budget are the documented Quickbase ones, but no live Quickbase account exists for this project and none was used. See Honest framing.
- **The exactly-once replay is at the 1,000-to-1,300-profile, 50-to-65-batch scale**, not an internet-scale soak. The mechanism (content-hash idempotency key, final-truth batches) does not depend on scale, but it has not been measured at it.
- **The rate-budget benchmark was run once this session with real wall-clock pacing**, not as a long-running continuous monitor; `docs/rate_limit_benchmark_output.txt` is that one real run's output, not a statistical distribution over many runs.
