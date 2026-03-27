from fastapi import FastAPI


app = FastAPI(title="XiaoBaiTu API", version="0.1.0")


@app.get("/health")
def health():
    return {"status": "ok"}
