# 102, Refund row missing from the order summary

## TL;DR

**Problem.** A reader who was refunded part of an order sees the original total, £42 instead of £30, and no refund line.
**Cause.** The summary adds up the order's payments and never reads the refunds recorded against it.
**Action.** Show every refund as its own line and subtract it from the total.
**Result.** The summary matches what the reader was actually charged.

## 3.1 Functional requirements

- **REQ-1** The order summary shall list every refund recorded against the order as a separate line.
- **REQ-2** The total shown on the order summary shall equal the payments less the refunds.

## 4.3 Verification cases

- **VC-1** `test`: an order with one payment and one refund shows both lines; verifies REQ-1. Red first: the refund line is absent on the unmodified code.
- **VC-2** `test`: the total on that order equals payment minus refund; verifies REQ-2.

## 4.4 Traceability

| Requirement | Verified by |
|---|---|
| REQ-1 | VC-1 |
| REQ-2 | VC-2 |

## 4.6 Acceptance criteria

- **AC-1** Order `ORD-1042` shows a refund line of 12.50 and a total of 29.50.

## Decisions taken

- Partial refunds are shown per refund, not summed (@alice, 2025-03-12).

<details><summary>Supporting material</summary>

### 1.1 Purpose

The summary on the order page is built in `storefront/src/orders/order_summary.py:12` from the order's payments only.

</details>

<!-- besman:spec-document -->
