from fastapi import APIRouter,UploadFile,File,HTTPException
from typing import List
import os
router=APIRouter()
MAX_FILE_SIZE_MB = 5 
@router.post("/upload")
async def upload_files(files:List[UploadFile]=File(...)):
    uploaded_files=[]
    os.makedirs("uploads",exist_ok=True)
    for file in files:
        if file.content_type!="application/pdf":
            raise HTTPException(status_code=400,details=f"{file.filename}is not a pdf")
        content=await file.read()
        if len(content)>MAX_FILE_SIZE_MB*1024*1024:
            raise HTTPException(status_code=400,detail=f"{file.filename}exceed 5MB size limit")
        save_path=os.path.join("uploads",file.filename)
        with open(save_path,"wb") as f:
            f.write(content)
        uploaded_files.append(file.filename)
    return{"message":"files uploaded successfully","files":uploaded_files}    


