from fastapi import FastAPI

app = FastAPI(title="groundwire")


@app.get("/")
def root():
    return {"message": "groundwire API is running"}


@app.get("/health")
def health():
    return {"status": "ok"}
