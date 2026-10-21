from fastapi import FastAPI

app = FastAPI(title="DealNest API")


@app.get("/health")
def health_check():
    return {
        "status": "ok",
        "service": "DealNest API"
    }