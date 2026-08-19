To decompress Gzip bodies, you can use `gunzipSync` from the `node:zlib` API to decompress and then read the body.

```ts

Deno.serve(async (req) => {
  try {
    // Check if the request body is gzip compressed
    const contentEncoding = req.headers.get('content-encoding')
    if (contentEncoding !== 'gzip') )
    }

    // Read the compressed body
    const compressedBody = await req.arrayBuffer()

    // Decompress the body
    const decompressedBody = gunzipSync(new Uint8Array(compressedBody))

    // Convert the decompressed body to a string
    const decompressedString = new TextDecoder().decode(decompressedBody)
    const data = JSON.parse(decompressedString)

    // Process the decompressed body as needed
    console.log(`Received: $`)

    return new Response('ok', ,
    })
  } catch (error) )
  }
})
```

Edge functions have a runtime memory limit of 150MB. Overly large compressed payloads may result in an out-of-memory error.