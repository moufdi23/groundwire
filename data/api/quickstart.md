This guide covers creating a REST route you can query using `cURL` or the browser by creating a database table called `leaderboard` to hold player scores. This creates a corresponding API route `/rest/v1/leaderboard` which can accept `GET`, `POST`, `PATCH`, and `DELETE` requests.

  
    

    [Create a new project](/dashboard/_) in the Supabase Dashboard.

After your project is ready, create a table in your Supabase database. You can do this with either the [Table Editor](/dashboard/project/_/editor) or the [SQL Editor](/dashboard/project/_/sql).

    </StepHikeCompact.Details>

    

      
      

      ```sql
      -- Create a "leaderboard" table to store
      -- player names and their scores.
      create table leaderboard (
        id serial primary key,
        player text not null,
        score integer not null default 0,
        created_at timestamptz default now()
      );
      ```

      
      

      1. Go to the [**Table editor**](/dashboard/project/_/editor) section in the Dashboard.
      2. Click **New Table** and create a table with the name `leaderboard`.
      3. Add a `player` column of type `text` and a `score` column of type `int4`.
      4. Click **Save**.

      
      

    </StepHikeCompact.Code>

  </StepHikeCompact.Step>

  
    

    Expose the `leaderboard` table through the Data API so it can be queried over HTTP. A leaderboard is meant to be public, so anonymous clients only need read access.

    For more control over which tables and functions are exposed, read the [Grant access explicitly guide](/docs/guides/api/securing-your-api#grant-access-explicitly).

    </StepHikeCompact.Details>

    

      
      

      ```sql
      -- Allow read-only access for anonymous clients
      grant select on public.leaderboard to anon;
      ```

      
      

      In the [**Integrations > Data API > Settings**](/dashboard/project/_/integrations/data_api/settings) section of the Dashboard. Under **Exposed schemas**, make sure `public` is included, then under **Exposed tables**, toggle on access for the `leaderboard` table.

      
      

    </StepHikeCompact.Code>

  </StepHikeCompact.Step>

  

    

    Enable Row Level Security (RLS) for this table and create the policies that control who can read and write rows. For a leaderboard, anyone should be able to read scores. Only authenticated users should be able to submit or update them.

    </StepHikeCompact.Details>

    

      ```sql
      -- Turn on RLS
      alter table "leaderboard"
      enable row level security;

      -- Anyone can read the leaderboard
      create policy "Leaderboard is public"
        on leaderboard
        for select
        to anon, authenticated
        using (true);

      -- Authenticated users can submit and update scores
      create policy "Authenticated users can submit scores"
        on leaderboard
        for insert
        to authenticated
        with check (true);

      create policy "Authenticated users can update scores"
        on leaderboard
        for update
        to authenticated
        using (true)
        with check (true);
      ```

    </StepHikeCompact.Code>

  </StepHikeCompact.Step>

  
    

    With RLS setup, grant write access to the `authenticated` and `service_role` roles.

    </StepHikeCompact.Details>

    

      ```sql
      -- Grant write access only after RLS and policies are in place
      grant select, insert, update, delete on public.leaderboard to authenticated;
      grant select, insert, update, delete on public.leaderboard to service_role;
      ```

    </StepHikeCompact.Code>

  </StepHikeCompact.Step>

  
    

    Now add some scores to the table so the API has something to query.

    </StepHikeCompact.Details>

    

      ```sql
      insert into leaderboard (player, score)
      values
        ('alice', 4200),
        ('bob', 3700),
        ('carol', 5100),
        ('dave', 2900);
      ```

    </StepHikeCompact.Code>

  </StepHikeCompact.Step>

  
    

    You can find your API URL and Keys in the [**Settings > API Settings**](/dashboard/project/_/settings/api) section of the Dashboard. Query the `leaderboard` table by appending `/rest/v1/leaderboard` to the API URL.

    Copy this block of code, substitute `` and ``, then run it from a terminal.

    </StepHikeCompact.Details>
    

      ```bash Terminal
      curl 'https://.supabase.co/rest/v1/leaderboard?select=*&order=score.desc' \
      -H "apikey: "
      ```

    </StepHikeCompact.Code>

  </StepHikeCompact.Step>

## Bonus

There are several options for accessing your data:

### Browser

You can query the route in your browser, by appending the `publishable` key as a query parameter:

`https://.supabase.co/rest/v1/leaderboard?apikey=`

### Curl

```sh
curl 'https://.supabase.co/rest/v1/leaderboard?select=*&order=score.desc' \
  -H "apikey: " \
```

### Client libraries

We provide a number of [Client Libraries](https://github.com/supabase/supabase#client-libraries).

```js
const  = await supabase
  .from('leaderboard')
  .select()
  .order('score', )
```

<$Show if="sdk:dart">

```dart
final data = await supabase
  .from('leaderboard')
  .select('*')
  .order('score', ascending: false);
```

</$Show>
<$Show if="sdk:python">

```python
response = (
    supabase.table('leaderboard')
    .select("*")
    .order('score', desc=True)
    .execute()
)
```

</$Show>
<$Show if="sdk:swift">

```swift
let response = try await supabase
  .from("leaderboard")
  .select()
  .order("score", ascending: false)
```

</$Show>
<$Show if="sdk:csharp">

```c#
[Table("leaderboard")]
class Leaderboard : BaseModel

    [Column("player")]
    public string Player 

    [Column("score")]
    public int Score 
}

var result = await supabase
  .From()
  .Order(x => x.Score, Ordering.Descending)
  .Get();
```

</$Show>