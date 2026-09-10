import os
from getpass import getpass
from passlib.context import CryptContext
from supabase import create_client, Client
from dotenv import load_dotenv

# Load keys from .env
load_dotenv()
SUPABASE_URL = os.environ.get("SUPABASE_URL")
SUPABASE_KEY = os.environ.get("SUPABASE_KEY")
supabase: Client = create_client(SUPABASE_URL, SUPABASE_KEY)

# Set up the encryption (hashing) context
pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")

print("\n--- Create Secure Superuser ---")
email = input("Enter Admin Email (e.g., katiekey1848@gmail.com): ")
password = getpass("Enter Secure Password (typing will be hidden): ")

# Encrypt the password
hashed_password = pwd_context.hash(password)

try:
    # Save the email and the ENCRYPTED password to the database
    supabase.table("admins").insert({
        "email": email, 
        "password_hash": hashed_password
    }).execute()
    print(f"\n✅ Success! Superuser '{email}' created.")
    print("Your password was securely encrypted. You can now log into the admin portal.\n")
except Exception as e:
    print(f"\n❌ Failed to create user. Error: {e}\n")