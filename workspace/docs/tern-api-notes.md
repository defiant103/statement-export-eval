# Tern core: API notes

Tern is the new core. Accounts are being migrated to it from Kestrel in waves.
These notes are from the vendor's onboarding pack and are brief.

## GetPostings

Request fields:

| Field | Meaning |
| --- | --- |
| `account_id` | The account to read |
| `from_date`, `to_date` | ISO dates, both inclusive. An invalid date is rejected |
| `cursor` | The cursor from the previous reply, to continue a list |

Reply fields: `postings` and `cursor`.

Each posting has:

| Field | Meaning |
| --- | --- |
| `posting_id` | Unique id of the posting |
| `value_date` | ISO date |
| `amount_minor` | Unsigned integer amount in minor units (cents) |
| `side` | `DEBIT` or `CREDIT`, as recorded on the ledger |
| `narrative` | Free text |
| `status` | `POSTED`, `PENDING` or `REJECTED` |
| `balance_after_minor` | The account balance once the posting has taken effect, in minor units. Null when it has not |

## Faults

Faults arrive as transport errors whose body is an object with an `error`
field, for example `account_not_found` or `invalid_date_range`.
