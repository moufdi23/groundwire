<$Partial path="quickstart_db_setup.mdx" />

## 3. Create an Expo app

Create a minimal Expo app using the `create-expo-app` command with the blank TypeScript template.

```bash
npx create-expo-app my-app --template blank-typescript
```

## 4. Set up AI tooling (optional)

<$Partial path="quickstart_ai_tooling.mdx" />

## 5. Install the Supabase client library

The fastest way to get started is to use the `@supabase/supabase-js` client library which provides a convenient interface for working with Supabase from a React Native app.

Navigate to the Expo app and install `supabase-js` along with the required dependencies for session storage and URL handling.

```bash
cd my-app && npx expo install @supabase/supabase-js react-native-url-polyfill expo-sqlite
```

## 6. Declare Supabase environment variables

Create a `.env` file in the root of your project and populate it with your Supabase connection variables that you can get from the helper below, or [from the project **Connect** panel](/dashboard/project/_?showConnect=true&connectTab=mobiles&framework=exporeactnative).

  <a href="/dashboard/project/_?showConnect=true&connectTab=mobiles&framework=exporeactnative">
    Open Connect panel
  </a>

Expo requires environment variables to be prefixed with `EXPO_PUBLIC_` to be accessible in your app code.

```text name=.env
EXPO_PUBLIC_SUPABASE_URL=
EXPO_PUBLIC_SUPABASE_PUBLISHABLE_KEY=
```

<$Partial path="api_settings.mdx" variables=} />

## 7. Initialize the Supabase client

Create a helper file at `lib/supabase.ts` to initialize the Supabase client using the environment variables.

The code below uses Expo's localStorage polyfill to persist authentication sessions.

```ts name=lib/supabase.ts

const supabaseUrl = process.env.EXPO_PUBLIC_SUPABASE_URL!
const supabasePublishableKey = process.env.EXPO_PUBLIC_SUPABASE_PUBLISHABLE_KEY!

export const supabase = createClient(supabaseUrl, supabasePublishableKey, {
  auth: ,
})
```

## 8. Query data from the app

Replace the contents of `App.tsx` with the following code to fetch and display the instruments from your database.

Use `useEffect` to fetch the data when the component mounts and display the query result using React Native components.

```tsx name=App.tsx

type Instrument = 

export default function App() {
  const [instruments, setInstruments] = useState([])
  const [error, setError] = useState<string | null>(null)

  useEffect(() => , [])

  async function getInstruments()  = await supabase.from('instruments').select()

    if (error) 

    setInstruments(data ?? [])
  }

  if (error) 
      
    )
  }

  return (
    
       item.id.toString()}
        renderItem=) => }
      />
    
  )
}

const styles = StyleSheet.create(,
  item: ,
})
```

## 9. Start the app

Run the development server and scan the QR code with the Expo Go app on your phone, or press `i` for iOS simulator or `a` for Android emulator.

```bash
npx expo start
```

<$Partial path="quickstart_going_to_production.mdx" />

## Next steps

- Set up [Auth](/docs/guides/auth) for your app
- [Insert more data](/docs/guides/database/import-data) into your database
- Upload and serve static files using [Storage](/docs/guides/storage)