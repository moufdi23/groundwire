Postgres supports flexible [array types](https://www.postgresql.org/docs/12/arrays.html). These arrays are also supported in the Supabase Dashboard and in the JavaScript API.

## Create a table with an array column

Create a test table with a text array (an array of strings):

1. Go to the [Table editor](/dashboard/project/_/editor) page in the Dashboard.
1. Click **New Table** and create a table with the name `arraytest`.
1. Click **Save**.
1. Click **New Column** and create a column with the name `textarray`, type `text`, and select **Define as array**.
1. Click **Save**.

```sql
create table arraytest (
  id integer not null,
  textarray text array
);
```

## Insert a record with an array value

1. Go to the [Table editor](/dashboard/project/_/editor) page in the Dashboard.
1. Select the `arraytest` table.
1. Click **Insert row** and add `["Harry", "Larry", "Moe"]`.
1. Click **Save.**

```sql
INSERT INTO arraytest (id, textarray) VALUES (1, ARRAY['Harry', 'Larry', 'Moe']);
```

Insert a record from the JavaScript client:

```js
const  = await supabase
  .from('arraytest')
  .insert([])
```

<$Show if="sdk:swift">

Insert a record from the Swift client:

```swift
struct ArrayTest: Encodable 

try await supabase
  .from("arraytest")
  .insert(
    [
      ArrayTest(
        id: 2,
        textarray: ["one", "two", "three", "four"]
      )
    ]
  )
  .execute()
```

</$Show>
<$Show if="sdk:python">

Insert a record from the Python client:

```python
supabase.from_('arraytest').insert(
  [
    
  ]
)
.execute()
```

</$Show>
<$Show if="sdk:csharp">

Insert a record from the C# client:

```c#
[Table("arraytest")]
class ArrayTest : BaseModel

    [Column("textarray")]
    public List<string> Textarray 
}

await supabase
  .From()
  .Insert(new ArrayTest  });
```

</$Show>

## View the results

1. Go to the [Table editor](/dashboard/project/_/editor) page in the Dashboard.
1. Select the `arraytest` table.

You should see:

```
| id  | textarray               |
| --- | ----------------------- |
| 1   | ["Harry","Larry","Moe"] |
```

```sql
select * from arraytest;
```

You should see:

```
| id  | textarray               |
| --- | ----------------------- |
| 1   | ["Harry","Larry","Moe"] |
```

## Query array data

Postgres uses 1-based indexing (e.g., `textarray[1]` is the first item in the array).

To select the first item from the array and get the total length of the array:

```js
SELECT textarray[1], array_length(textarray, 1) FROM arraytest;
```

returns:

```
| textarray | array_length |
| --------- | ------------ |
| Harry     | 3            |
```

This returns the entire array field:

```js
const  = await supabase.from('arraytest').select('textarray')
console.log(JSON.stringify(data, null, 2))
```

returns:

```json
[
  
]
```

<$Show if="sdk:swift">

This returns the entire array field:

```swift
struct Response: Decodable 

let response: [Response] = try await supabase.from("arraytest").select("textarray").execute().value
dump(response)
```

returns:

```
[
  Response(
    textarray: ["Harry", "Larry", "Moe"],
  )
]
```

</$Show>
<$Show if="sdk:csharp">

This returns the entire array field:

```c#
var result = await supabase
  .From()
  .Select(x => new object[] )
  .Get();
```

</$Show>

## Resources

- [Supabase JS Client](https://github.com/supabase/supabase-js)
- [Supabase - Get started for free](https://supabase.com)
- [Postgres Arrays](https://www.postgresql.org/docs/15/arrays.html)