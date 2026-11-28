# Jedha core: API notes

Jedha is the legacy core. This service uses two of its operations.

## ListTransactions

Request fields:

| Field | Meaning |
| --- | --- |
| `account_id` | The account to read |
| `period` | `YYYY-MM` |
| `page_size` | Rows per page, 1 to 100 |
| `page_token` | Token from the previous reply, to continue a list |
| `skip` | Number of rows to skip |

Reply fields: `items` (each with `id`, `posted`, `description`, `amount`), `total`
(the number of rows that match the query) and `next_token` (absent or null on
the last page).

`amount` is a decimal string, signed from the member's point of view: a deposit
is positive and a withdrawal is negative.

## ListHolds

Lists the holds currently placed on an account. Request fields are `account_id`,
`page_size`, `page_token` and `skip`, with the same meaning as above. Reply
fields are `items` (each with `id`, `placed`, `reason`, `amount`), `total` and
`next_token`.

## Faults

Faults arrive as transport errors with a `K-nnn` code in the body. `K-404` is
an unknown account. `K-503` means the core is unavailable and can occur on any
call.
