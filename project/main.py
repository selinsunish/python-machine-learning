from fastapi import FastAPI
from upload import router as upload_router
print("✅ Running actual main.py")
app=FastAPI()
app.include_router(upload_router)

