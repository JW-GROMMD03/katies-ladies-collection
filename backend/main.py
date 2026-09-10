import os
import time
import boto3
import jwt
from datetime import datetime, timedelta
from contextlib import asynccontextmanager
from fastapi import FastAPI, Request, HTTPException, Depends, File, UploadFile, Form, Header
from fastapi.middleware.cors import CORSMiddleware
from supabase import create_client, Client
from pydantic import BaseModel
from typing import Optional
from fastapi_cache import FastAPICache
from fastapi_cache.backends.inmemory import InMemoryBackend
from fastapi_cache.decorator import cache
from dotenv import load_dotenv
from passlib.context import CryptContext

load_dotenv()

# --- Configs ---
SUPABASE_URL = os.environ.get("SUPABASE_URL")
SUPABASE_KEY = os.environ.get("SUPABASE_KEY")
supabase: Client = create_client(SUPABASE_URL, SUPABASE_KEY)
JWT_SECRET = os.environ.get("JWT_SECRET", "super-secret-key-change-this")

# Password Hashing Context
pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")

# Cloudflare R2 Config
s3_client = boto3.client('s3',
    endpoint_url=f"https://{os.environ.get('CF_ACCOUNT_ID')}.r2.cloudflarestorage.com",
    aws_access_key_id=os.environ.get('CF_ACCESS_KEY'),
    aws_secret_access_key=os.environ.get('CF_SECRET_KEY')
)

@asynccontextmanager
async def lifespan(app: FastAPI):
    FastAPICache.init(InMemoryBackend(), prefix="katies-cache")
    yield

app = FastAPI(title="Katie's Ladies API", lifespan=lifespan)
app.add_middleware(
    CORSMiddleware, 
    allow_origins=["*"], 
    allow_credentials=True, 
    allow_methods=["*"], 
    allow_headers=["*"]
)

# --- Models ---
class LoginRequest(BaseModel):
    email: str
    password: str

class StatusUpdate(BaseModel):
    status: str

# --- JWT Verification Dependency ---
def verify_token(authorization: Optional[str] = Header(None)):
    if not authorization or not authorization.startswith("Bearer "):
        raise HTTPException(status_code=401, detail="Missing or invalid authentication token")
    
    token = authorization.split(" ")[1]
    try:
        payload = jwt.decode(token, JWT_SECRET, algorithms=["HS256"])
        return payload["sub"]
    except jwt.ExpiredSignatureError:
        raise HTTPException(status_code=401, detail="Session expired. Please log in again.")
    except jwt.InvalidTokenError:
        raise HTTPException(status_code=401, detail="Invalid token")

# --- SECURE AUTH ENDPOINT ---
@app.post("/api/auth/login")
async def login(req: LoginRequest):
    # Fetch admin from Supabase
    user_res = supabase.table("admins").select("*").eq("email", req.email).execute()
    
    if not user_res.data:
        raise HTTPException(status_code=401, detail="Invalid email or password")
    
    user_data = user_res.data[0]
    
    # Verify password hash
    is_valid = pwd_context.verify(req.password, user_data["password_hash"])
    if not is_valid:
        raise HTTPException(status_code=401, detail="Invalid email or password")
    
    # Generate Token
    token = jwt.encode(
        {"sub": req.email, "exp": datetime.utcnow() + timedelta(hours=12)}, 
        JWT_SECRET, 
        algorithm="HS256"
    )
    return {"token": token}

# --- CUSTOMER ENDPOINTS (CACHED & PUBLIC) ---
@app.get("/api/products")
@cache(expire=300) 
async def get_products(type: Optional[str] = None, brand: Optional[str] = None):
    query = supabase.table("products").select("*")
    if type: query = query.eq("type", type)
    if brand: query = query.ilike("brand", f"%{brand}%")
    res = query.order("created_at", desc=True).execute()
    return res.data

@app.post("/api/products/{product_id}/view")
async def increment_view(product_id: str):
    item = supabase.table("products").select("views").eq("id", product_id).execute()
    if item.data:
        supabase.table("products").update({"views": item.data[0]["views"] + 1}).eq("id", product_id).execute()
    return {"status": "success"}

# --- ADMIN ENDPOINTS (PROTECTED) ---
@app.post("/api/admin/products")
async def add_product(
    name: str = Form(...),
    brand: Optional[str] = Form(""),
    price: float = Form(...),
    original_price: Optional[float] = Form(None),
    type: str = Form(...),
    category: str = Form(...),
    color: str = Form(...),
    file: UploadFile = File(...),
    admin_email: str = Depends(verify_token) # Secures the route
):
    file_extension = file.filename.split(".")[-1]
    file_key = f"products/{int(time.time())}.{file_extension}"
    
    s3_client.upload_fileobj(file.file, os.environ.get('CF_BUCKET_NAME'), file_key, ExtraArgs={'ACL': 'public-read'})
    image_url = f"{os.environ.get('CF_PUBLIC_URL')}/{file_key}"
    
    product_data = {
        "name": name, "brand": brand, "price": price, 
        "original_price": original_price, "type": type, 
        "category": category, "color": color, "image_url": image_url
    }
    res = supabase.table("products").insert(product_data).execute()
    await FastAPICache.clear() 
    return res.data

@app.patch("/api/admin/products/{product_id}/status")
async def update_status(
    product_id: str, 
    payload: StatusUpdate,
    admin_email: str = Depends(verify_token) # Secures the route
):
    res = supabase.table("products").update({"status": payload.status}).eq("id", product_id).execute()
    await FastAPICache.clear()
    return res.data