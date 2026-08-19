Every `supabase-js` call returns a `` pair instead of throwing. When something fails, the single most useful field on `error` is usually `hint` — Postgres returns the _fix_, not only a description of the problem. Logging only `error.message` hides it.

## Usage of `message` and `hint` properties

Consider a `42501` permission-denied error on a table where default `GRANT`s have been revoked from `anon`:

```
message: "permission denied for table users"
hint:    "Grant the required privileges to the current role with: GRANT SELECT ON public.users TO anon;"
```

The `message` exposes the error reason, and `hint` gives you the literal SQL statement to run in the dashboard SQL editor to fix it.

The same pattern shows up across many Postgres errors — missing column? `hint` suggests the column name you probably meant. Type mismatch? `hint` shows the expected type. Whenever Postgres knows the fix, it puts it in `hint`.

Log the full `error` object, not only `error.message`.

## The recommended pattern

Read `` from the response, check `error`, log the whole object, and return early.

```ts
const  = await supabase.from('users').select()
if (error) 
```

In the case of a permission-denied error, the response body will look like this:

```json
{
  "error": {
    "code": "42501",
    "message": "permission denied for table users",
    "details": null,
    "hint": "Grant the required privileges to the current role with: GRANT SELECT ON public.users TO anon;"
  },
  "status": 401,
  "statusText": "Unauthorized"
}
```

`postgrest-js` passes the body through verbatim, so `error.hint` is the exact string Postgres produced. Treat it as the answer the database is giving you, not as a suggestion to file away.

## The `PostgrestError` fields, by usefulness

Database calls (`select`, `insert`, `update`, `upsert`, `delete`, `rpc`) return a `PostgrestError` with four fields. Read them in roughly this order:

| Field     | Read it when                                                                                                       |
| --------- | ------------------------------------------------------------------------------------------------------------------ |
| `hint`    | Always check first. When Postgres includes one, it's the actionable fix (a `GRANT` to run, a column name, a type). |
| `code`    | When branching in code. Codes are stable across versions; `message` text isn't.                                    |
| `details` | When `hint` and `message` aren't enough. Often contains the offending value, key, or row.                          |
| `message` | As the human summary. Useful in UI strings, less useful for debugging.                                             |

A full list of PostgREST error codes is in the [Error Codes reference](/guides/api/rest/postgrest-error-codes).

## Branch on `error.code`, not `error.message`

`error.code` is more reliable than `error.message` for programmatic branching: messages change between Postgres and PostgREST versions, but codes are stable.

```ts
const  = await supabase.from('users').select()
if (error) {
  console.error(error)
  if (error.code === '42501') 
  return
}
```

## Errors from Auth, Storage, and Edge Functions

The same rule applies across the SDK — log the whole error object — but the shape differs by client.

### Auth

`AuthError` exposes `error.code` (e.g. `'invalid_credentials'`, `'email_not_confirmed'`) and `error.status`. Branch on `code`; log the whole thing.

```ts
const  = await supabase.auth.signInWithPassword()
if (error) 
```

### Storage

`StorageError` exposes `error.statusCode` (HTTP status as a string) and a structured `error` name (e.g. `'Duplicate'`, `'NotFound'`).

```ts
const  = await supabase.storage
  .from('avatars')
  .upload('public/avatar1.png', avatarFile)
if (error) 
```

### Edge Functions

Functions errors arrive as one of three subclasses. Narrow with `instanceof`; for `FunctionsHttpError`, parse the body to get the function's own error payload.

```ts

const  = await supabase.functions.invoke('hello')
if (error instanceof FunctionsHttpError)  else if (error) 
```

### Realtime

The `subscribe()` callback receives a `status` and, on failure, an `err` argument. Log the whole `err` — its `cause` often holds the underlying reason.

```ts
supabase.channel('room1').subscribe((status, err) => 
})
```

## Related

- [PostgREST Error Codes](/guides/api/rest/postgrest-error-codes)
- [Automatic retries with `supabase-js`](/guides/api/automatic-retries-in-supabase-js)
- [Securing your API](/guides/api/securing-your-api)