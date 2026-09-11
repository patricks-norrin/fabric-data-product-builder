# SCD2 Supported Scenarios

This page demonstrates the supported SCD2 behaviors for `upsert_delta_change_history(...)` using compact sample data.

## Scope And Assumptions

| Item | Value |
| --- | --- |
| Business key | `dpmeta_uid` |
| Version start | `dpmeta_object_version_start_time` (derived from `modified_at`) |
| Change detection | `dpmeta_payload_hash` changes when payload columns change |
| Current record flag | `dpmeta_is_current = true` only for latest active row per uid |
| Version end | `dpmeta_object_version_end_time` is set to next version start |

Sample payload columns in this page: `name`, `tier`, `city`.

---

## 1. New UID Arrives

When a new `dpmeta_uid` appears, it is appended. Existing UIDs are not modified.

### Existing Change History (before)

| dpmeta_uid | name | tier | city | start_time | end_time | is_current |
| --- | --- | --- | --- | --- | --- | --- |
| U1 | Acme | Silver | Helsinki | 2024-01-01 00:00:00 | null | true |

### Incoming Batch

| dpmeta_uid | name | tier | city | modified_at |
| --- | --- | --- | --- | --- |
| U2 | Bravo | Bronze | Tampere | 2024-02-01 00:00:00 |

### Expected Change History (after)

| dpmeta_uid | name | tier | city | start_time | end_time | is_current |
| --- | --- | --- | --- | --- | --- | --- |
| U1 | Acme | Silver | Helsinki | 2024-01-01 00:00:00 | null | true |
| U2 | Bravo | Bronze | Tampere | 2024-02-01 00:00:00 | null | true |

---

## 2A. Existing UID Updated (Single Column Changed)

When one payload column changes, a new version is added and previous current version is closed.

### Existing Change History (before)

| dpmeta_uid | name | tier | city | start_time | end_time | is_current |
| --- | --- | --- | --- | --- | --- | --- |
| U1 | Acme | Silver | Helsinki | 2024-01-01 00:00:00 | null | true |

### Incoming Batch

| dpmeta_uid | name | tier | city | modified_at |
| --- | --- | --- | --- | --- |
| U1 | Acme | Gold | Helsinki | 2024-03-01 00:00:00 |

### Expected Change History (after)

| dpmeta_uid | name | tier | city | start_time | end_time | is_current |
| --- | --- | --- | --- | --- | --- | --- |
| U1 | Acme | Silver | Helsinki | 2024-01-01 00:00:00 | 2024-03-01 00:00:00 | false |
| U1 | Acme | Gold | Helsinki | 2024-03-01 00:00:00 | null | true |

Notes:
- `dpmeta_payload_hash` differs between Silver and Gold rows.
- The new row is current; the previous row gets end time and `is_current=false`.

---

## 2B. Existing UID Updated (Multiple Columns Changed)

If multiple payload columns change, behavior is identical: insert a new version and close the old one.

### Existing Change History (before)

| dpmeta_uid | name | tier | city | start_time | end_time | is_current |
| --- | --- | --- | --- | --- | --- | --- |
| U1 | Acme | Gold | Helsinki | 2024-03-01 00:00:00 | null | true |

### Incoming Batch

| dpmeta_uid | name | tier | city | modified_at |
| --- | --- | --- | --- | --- |
| U1 | Acme Oy | Platinum | Espoo | 2024-04-01 00:00:00 |

### Expected Change History (after)

| dpmeta_uid | name | tier | city | start_time | end_time | is_current |
| --- | --- | --- | --- | --- | --- | --- |
| U1 | Acme | Gold | Helsinki | 2024-03-01 00:00:00 | 2024-04-01 00:00:00 | false |
| U1 | Acme Oy | Platinum | Espoo | 2024-04-01 00:00:00 | null | true |

---

## 3. Out-Of-Order Arrival

If a version arrives late with a timestamp between existing versions, it is inserted in the middle of the history.

### Existing Change History (before)

| dpmeta_uid | name | tier | city | start_time | end_time | is_current |
| --- | --- | --- | --- | --- | --- | --- |
| U1 | Acme | Silver | Helsinki | 2024-01-01 00:00:00 | 2024-05-01 00:00:00 | false |
| U1 | Acme | Platinum | Helsinki | 2024-05-01 00:00:00 | null | true |

### Incoming Batch (late event)

| dpmeta_uid | name | tier | city | modified_at |
| --- | --- | --- | --- | --- |
| U1 | Acme | Gold | Helsinki | 2024-03-01 00:00:00 |

### Expected Change History (after)

| dpmeta_uid | name | tier | city | start_time | end_time | is_current |
| --- | --- | --- | --- | --- | --- | --- |
| U1 | Acme | Silver | Helsinki | 2024-01-01 00:00:00 | 2024-03-01 00:00:00 | false |
| U1 | Acme | Gold | Helsinki | 2024-03-01 00:00:00 | 2024-05-01 00:00:00 | false |
| U1 | Acme | Platinum | Helsinki | 2024-05-01 00:00:00 | null | true |

---

## 4. History Backfill

If older historical data is loaded after initial processing, it is added as an earlier version and the earliest existing row is closed accordingly.

### Existing Change History (before)

| dpmeta_uid | name | tier | city | start_time | end_time | is_current |
| --- | --- | --- | --- | --- | --- | --- |
| U1 | Acme | Silver | Helsinki | 2024-02-01 00:00:00 | null | true |

### Incoming Batch (backfill)

| dpmeta_uid | name | tier | city | modified_at |
| --- | --- | --- | --- | --- |
| U1 | Acme | Bronze | Helsinki | 2024-01-01 00:00:00 |

### Expected Change History (after)

| dpmeta_uid | name | tier | city | start_time | end_time | is_current |
| --- | --- | --- | --- | --- | --- | --- |
| U1 | Acme | Bronze | Helsinki | 2024-01-01 00:00:00 | 2024-02-01 00:00:00 | false |
| U1 | Acme | Silver | Helsinki | 2024-02-01 00:00:00 | null | true |

---

## 5. Reversed Update (Revert To Previous Payload)

If an entity changes back to a previously seen business payload at a newer timestamp, it is still a new SCD2 version.

### Existing Change History (before)

| dpmeta_uid | name | tier | city | start_time | end_time | is_current |
| --- | --- | --- | --- | --- | --- | --- |
| U1 | Acme | Silver | Helsinki | 2024-01-01 00:00:00 | 2024-05-01 00:00:00 | false |
| U1 | Acme | Gold | Helsinki | 2024-05-01 00:00:00 | null | true |

### Incoming Batch (revert)

| dpmeta_uid | name | tier | city | modified_at |
| --- | --- | --- | --- | --- |
| U1 | Acme | Silver | Helsinki | 2024-06-01 00:00:00 |

### Expected Change History (after)

| dpmeta_uid | name | tier | city | start_time | end_time | is_current |
| --- | --- | --- | --- | --- | --- | --- |
| U1 | Acme | Silver | Helsinki | 2024-01-01 00:00:00 | 2024-05-01 00:00:00 | false |
| U1 | Acme | Gold | Helsinki | 2024-05-01 00:00:00 | 2024-06-01 00:00:00 | false |
| U1 | Acme | Silver | Helsinki | 2024-06-01 00:00:00 | null | true |

Notes:
- This is not treated as an in-place update of the first Silver row.
- A new row version is inserted because this is a new event in time.

---

## 6. Documented Test Case: Ended Record Gets Reactivated

Use this as a direct pytest scenario definition.

### Test Name Suggestion

`test_reactivated_ended_record_becomes_new_current_version`

### Given

| dpmeta_uid | status | start_time | end_time | is_current |
| --- | --- | --- | --- | --- |
| U9 | inactive | 2024-01-01 00:00:00 | 2024-03-01 00:00:00 | false |
| U9 | active | 2024-03-01 00:00:00 | null | true |

### When

Incoming row reactivates the previously ended business state at a newer timestamp.

| dpmeta_uid | status | modified_at |
| --- | --- | --- |
| U9 | inactive | 2024-06-01 00:00:00 |

### Then

| dpmeta_uid | status | start_time | end_time | is_current |
| --- | --- | --- | --- | --- |
| U9 | inactive | 2024-01-01 00:00:00 | 2024-03-01 00:00:00 | false |
| U9 | active | 2024-03-01 00:00:00 | 2024-06-01 00:00:00 | false |
| U9 | inactive | 2024-06-01 00:00:00 | null | true |

### Assertions

| Assertion | Expected |
| --- | --- |
| New row count delta | +1 for uid U9 |
| Previously current row closure | `end_time = 2024-06-01 00:00:00` and `is_current = false` |
| Reactivated row | newest row with `status=inactive`, `is_current=true`, `end_time=null` |
| Historical row integrity | old ended row (2024-01-01 -> 2024-03-01) remains unchanged |

---

## 7. Documented Test Cases For Edge Conditions

### 7.1 No-Op Idempotency For Exact Duplicate Event

Test name suggestion: `test_exact_duplicate_event_is_noop`

Given

| dpmeta_uid | status | start_time | end_time | is_current |
| --- | --- | --- | --- | --- |
| U1 | active | 2024-01-01 00:00:00 | null | true |

When

| dpmeta_uid | status | modified_at |
| --- | --- | --- |
| U1 | active | 2024-01-01 00:00:00 |

Then

| dpmeta_uid | status | start_time | end_time | is_current |
| --- | --- | --- | --- | --- |
| U1 | active | 2024-01-01 00:00:00 | null | true |

Assertions

| Assertion | Expected |
| --- | --- |
| Row count | unchanged |
| Current row | unchanged |
| End timestamps | unchanged |

### 7.2 Same Payload With Newer Timestamp

Test name suggestion: `test_same_payload_newer_timestamp_follows_checksum_policy`

Given

| dpmeta_uid | status | start_time | end_time | is_current |
| --- | --- | --- | --- | --- |
| U2 | active | 2024-01-01 00:00:00 | null | true |

When

| dpmeta_uid | status | modified_at |
| --- | --- | --- |
| U2 | active | 2024-02-01 00:00:00 |

Then

Case A: timestamp included in payload hash

| dpmeta_uid | status | start_time | end_time | is_current |
| --- | --- | --- | --- | --- |
| U2 | active | 2024-01-01 00:00:00 | 2024-02-01 00:00:00 | false |
| U2 | active | 2024-02-01 00:00:00 | null | true |

Case B: timestamp excluded from payload hash

| dpmeta_uid | status | start_time | end_time | is_current |
| --- | --- | --- | --- | --- |
| U2 | active | 2024-01-01 00:00:00 | null | true |

Assertions

| Policy | Expected |
| --- | --- |
| Timestamp included in payload hash | new version row is created |
| Timestamp excluded from payload hash | no new version row |

### 7.3 Multi-UID Mixed Batch

Test name suggestion: `test_mixed_batch_processes_each_uid_independently`

Given

| dpmeta_uid | status | start_time | end_time | is_current |
| --- | --- | --- | --- | --- |
| U1 | active | 2024-01-01 00:00:00 | null | true |
| U2 | bronze | 2024-01-01 00:00:00 | null | true |

When

| dpmeta_uid | status | modified_at | scenario |
| --- | --- | --- | --- |
| U1 | active | 2024-01-01 00:00:00 | unchanged |
| U2 | silver | 2024-02-01 00:00:00 | changed |
| U3 | active | 2024-02-01 00:00:00 | new |

Then

| dpmeta_uid | status | start_time | end_time | is_current |
| --- | --- | --- | --- | --- |
| U1 | active | 2024-01-01 00:00:00 | null | true |
| U2 | bronze | 2024-01-01 00:00:00 | 2024-02-01 00:00:00 | false |
| U2 | silver | 2024-02-01 00:00:00 | null | true |
| U3 | active | 2024-02-01 00:00:00 | null | true |

Assertions

| Assertion | Expected |
| --- | --- |
| U1 | unchanged history |
| U2 | previous row closed and new current row added |
| U3 | inserted as new current row |

### 7.4 Multiple Versions For Same UID In One Batch

Test name suggestion: `test_multiple_incoming_versions_same_uid_chain_correctly`

Given

| dpmeta_uid | status | start_time | end_time | is_current |
| --- | --- | --- | --- | --- |
| U4 | v1 | 2024-01-01 00:00:00 | null | true |

When

| dpmeta_uid | status | modified_at |
| --- | --- | --- |
| U4 | v2 | 2024-02-01 00:00:00 |
| U4 | v3 | 2024-03-01 00:00:00 |

Then

| dpmeta_uid | status | start_time | end_time | is_current |
| --- | --- | --- | --- | --- |
| U4 | v1 | 2024-01-01 00:00:00 | 2024-02-01 00:00:00 | false |
| U4 | v2 | 2024-02-01 00:00:00 | 2024-03-01 00:00:00 | false |
| U4 | v3 | 2024-03-01 00:00:00 | null | true |

Assertions

| Assertion | Expected |
| --- | --- |
| Version order | v1 -> v2 -> v3 |
| End times | v1 ends at 2024-02-01, v2 ends at 2024-03-01 |
| Current row | only v3 is current |

### 7.5 Same Timestamp Collision For Same UID

Test name suggestion: `test_same_timestamp_collision_has_deterministic_behavior`

Given

| dpmeta_uid | status | start_time | end_time | is_current |
| --- | --- | --- | --- | --- |
| U5 | old | 2024-01-01 00:00:00 | null | true |

When

| dpmeta_uid | status | modified_at |
| --- | --- | --- |
| U5 | value_a | 2024-02-01 00:00:00 |
| U5 | value_b | 2024-02-01 00:00:00 |

Then

Example expected table when collisions are accepted and ordering is deterministic:

| dpmeta_uid | status | start_time | end_time | is_current |
| --- | --- | --- | --- | --- |
| U5 | old | 2024-01-01 00:00:00 | 2024-02-01 00:00:00 | false |
| U5 | value_a | 2024-02-01 00:00:00 | 2024-02-01 00:00:00 | false |
| U5 | value_b | 2024-02-01 00:00:00 | null | true |

If the chosen project policy is to reject collisions, then no expected history table is produced and the test should assert a failure instead.

Assertions

| Assertion | Expected |
| --- | --- |
| Behavior | deterministic and documented for project policy |
| Test result | assert exact chosen policy (accept one, reject batch, or tie-break rule) |

### 7.6 Null Transition In Payload

Test name suggestion: `test_null_value_transitions_create_versions`

Given

| dpmeta_uid | city | start_time | end_time | is_current |
| --- | --- | --- | --- | --- |
| U6 | null | 2024-01-01 00:00:00 | null | true |

When

| dpmeta_uid | city | modified_at |
| --- | --- | --- |
| U6 | Helsinki | 2024-02-01 00:00:00 |
| U6 | null | 2024-03-01 00:00:00 |

Then

| dpmeta_uid | city | start_time | end_time | is_current |
| --- | --- | --- | --- | --- |
| U6 | null | 2024-01-01 00:00:00 | 2024-02-01 00:00:00 | false |
| U6 | Helsinki | 2024-02-01 00:00:00 | 2024-03-01 00:00:00 | false |
| U6 | null | 2024-03-01 00:00:00 | null | true |

Assertions

| Assertion | Expected |
| --- | --- |
| Null -> value | creates new version |
| Value -> null | creates new version |
| Current row | latest event is current |

### 7.7 Backfill Older Than Current Oldest Row

Test name suggestion: `test_backfill_older_than_oldest_prepends_history`

Given

| dpmeta_uid | status | start_time | end_time | is_current |
| --- | --- | --- | --- | --- |
| U7 | silver | 2024-02-01 00:00:00 | null | true |

When

| dpmeta_uid | status | modified_at |
| --- | --- | --- |
| U7 | bronze | 2024-01-01 00:00:00 |

Then

| dpmeta_uid | status | start_time | end_time | is_current |
| --- | --- | --- | --- | --- |
| U7 | bronze | 2024-01-01 00:00:00 | 2024-02-01 00:00:00 | false |
| U7 | silver | 2024-02-01 00:00:00 | null | true |

Assertions

| Assertion | Expected |
| --- | --- |
| Earliest row | new bronze row at 2024-01-01 |
| Boundary update | bronze ends at 2024-02-01 |
| Current row | silver remains current |

### 7.8 Post-Run Invariant Test

Test name suggestion: `test_scd2_invariants_hold_after_each_scenario`

Apply these checks after each scenario-specific test.

| Invariant | Check |
| --- | --- |
| One current row | count rows where `dpmeta_is_current=true` equals 1 per uid |
| Current end time | current row has null `dpmeta_object_version_end_time` |
| Non-current end times | non-current rows have non-null end_time |
| Timeline continuity | ordered rows satisfy previous end_time = next start_time |
| Monotonic starts | `dpmeta_object_version_start_time` increases within each uid |

---

## Validation Checklist For Tests

Use this checklist in pytest assertions for each scenario.

| Check | Expected |
| --- | --- |
| One current row per uid | Exactly one row where `dpmeta_is_current=true` |
| Current row end time | `dpmeta_object_version_end_time` is null |
| Previous rows end times | Non-null and aligned to next version start time |
| New version on payload change | New row inserted when payload hash changes |
| No mutation for unrelated uid | Existing rows for other uids remain unchanged |
