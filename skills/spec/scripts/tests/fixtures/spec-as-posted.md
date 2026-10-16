# 101 — Hold a reserved book for 48 hours before releasing it

## TL;DR

**Problem.** A reader reserves the last copy of a title and finds it sold at the counter an hour later; the hold lasts `0` hours.
**Cause.** A reservation records the reader's wish but marks no copy, so the till and the website both treat the copy as free.
**Action.** Mark one copy as held for 48 opening hours, keep it out of every sale, and return it to the shelf when the hold ends.
**Result.** Readers collect what they reserved, and unclaimed copies go back on sale without anyone clearing them by hand.

---

## 3.1 Functional requirements

**S** = copies of the title in the shop; **H** = copies held for a reader; **free** = S − H.

- **REQ-1** When a reader reserves a title with at least one free copy, the system shall mark exactly one copy as held for that reader.
- **REQ-2** When a reader reserves a title with no free copy, the system shall place the reservation on the waiting list without marking a copy.
- **REQ-3** A held copy shall be refused by the till for any reader other than the one it is held for.
  > The till already refuses a copy flagged as damaged; the held flag follows the same path.
- **REQ-4** A held copy shall not be offered for sale or reservation on the website.
- **REQ-5** A hold shall end 48 opening hours after it began, counted only while the shop is open.
  > Opening hours already exist per shop; a public holiday counts as closed.
- **REQ-6** When a hold ends uncollected, the copy shall return to the free stock within ten minutes.
- **REQ-7** When a held copy returns to the free stock and the waiting list for its title is not empty, the system shall hold it for the first reader on that list.
- **REQ-8** The reading copy shall never be marked as held.
- **REQ-9** The availability line on the title page shall show free copies and held copies as two numbers.
- **REQ-10** The system shall email the reader when a hold begins, stating the collection deadline in the shop's local time.
- **REQ-11** The system shall email the reader when a hold ends uncollected.
- **REQ-12** Holds shall apply only to reservations made on or after the release; earlier reservations keep their current behaviour.

### 3.3 Software system attributes

- **ATT-1** Ending expired holds shall take no longer as the number of titles in the catalogue grows.

---

## 4.3 Verification cases

All red first except the guard VC-12.

- **VC-1** `test` — reserving a title with two free copies holds exactly one; the other stays free. (REQ-1)
- **VC-2** `test` — reserving a title with no free copy adds the reader to the waiting list and holds nothing. (REQ-2)
- **VC-3** `test` — the till refuses a held copy for another reader and accepts it for the holder. (REQ-3)
- **VC-4** `test` — the website neither sells nor reserves a held copy. (REQ-4)
- **VC-5** `test` — a hold placed on Saturday evening ends on Tuesday, given the shop is closed on Sunday and Monday. (REQ-5)
- **VC-6** `test` — an expired hold returns its copy to the free stock in the next expiry run. (REQ-6)
- **VC-7** `test` — an expired hold with a waiting list moves the copy to the first reader on it. (REQ-7)
- **VC-8** `test` — reserving a title whose only copy is the reading copy holds nothing. (REQ-8)
- **VC-9** `test` — a title with three copies, one held, shows two free and one held. (REQ-9)
- **VC-10** `test` — a new hold sends one email with the deadline in local time; an expired one sends one more. (REQ-10, REQ-11)
- **VC-11** `test` — a reservation made before the release holds no copy; an identical later one does. (REQ-12)
- **VC-12** `analysis` — the expiry run reads only holds that have ended, never the whole catalogue. (ATT-1)

### 4.4 Traceability

REQ-1 → VC-1 · REQ-2 → VC-2 · REQ-3 → VC-3 · REQ-4 → VC-4 · REQ-5 → VC-5 · REQ-6 → VC-6 · REQ-7 → VC-7 · REQ-8 → VC-8 · REQ-9 → VC-9 · REQ-10 → VC-10 · REQ-11 → VC-10 · REQ-12 → VC-11 · ATT-1 → VC-12. No holes.

### 4.6 Acceptance criteria

- **AC-1** A reader who reserves the last copy finds it held at the desk the next day, and the till will not sell it to anyone else.
- **AC-2** A hold placed before a closed weekend still has time left when the shop reopens.
- **AC-3** An uncollected copy is back on sale without staff action, or goes to the next reader waiting.
- **AC-4** The reading copy is never reserved.
- **AC-5** A reservation made before the release behaves as it did.

---

## Decisions taken

All **@bob**, 2025-03-12, on the ticket; quoted as given.

| # | Answer as given | Effect |
|---|---|---|
| Q1 hold clock | A — count opening hours only | REQ-5 |
| Q2 reading copy | "The reading copy never leaves the shop, so it is never held" | REQ-8 |
| Q3 availability | B — show held copies separately | REQ-9 |
| Q4 existing reservations | "Only new ones." | REQ-12 |

## Open items

- **O-1** Wording of the two emails — @alice, before release. REQ-10 and REQ-11 fix what they say, not how.
- **O-2** `UNKNOWN` — whether any shop records opening hours in a time zone other than its own.

---

<details>
<summary><b>Supporting material</b></summary>

### 1.1 Purpose

Turn a reservation into a hold on one physical copy, so the till and the website stop selling a copy a reader was promised, and release that copy automatically when the reader does not come.

### 1.2 Scope

**In scope:** reservations made on the website and at the desk; the till's refusal; the title page's availability line; the two emails.

**Out of scope, with reasons:**
- E-book loans — they have no physical copy and already expire on their own (`storefront/src/ebooks/loan_expiry.py:20-31`).
- Inter-shop transfers — a different flow with its own hold (`storefront/src/transfers/transfer_hold.py:14`).

### 1.3 Limitations that remain

- **L-1** A reader who reserves at the desk while the website shows the same copy free may still lose a race of a few seconds.
- **L-2** Shops without recorded opening hours fall back to counting every hour.

### 5.1 Assumptions and dependencies

- **A-1** `INFERRED` — every shop has opening hours recorded; the shop table requires them (`storefront/src/shops/shop.py:41`).

<details>
<summary><b>Investigation evidence</b></summary>

| Fact | Citation | Confidence |
|---|---|---|
| A reservation stores the title and the reader, no copy | `storefront/src/reservations/reservation.py:12-30` | VERIFIED |
| The till refuses only damaged copies | `till/src/checkout/held_copies.py:16` | VERIFIED |
| The expiry job runs every ten minutes | `storefront/src/reservations/hold_expiry.py:8` | VERIFIED |

</details>
</details>
