from supabase import create_client
import os
from dotenv import load_dotenv

load_dotenv()

SUPABASE_URL = os.getenv("SUPABASE_URL")
SUPABASE_KEY = os.getenv("SUPABASE_KEY")

supabase = create_client(SUPABASE_URL, SUPABASE_KEY)

result = supabase.auth.sign_in_with_password({
    "email": "test1@example.com",
    "password": "user1"
})

print("ACCESS TOKEN:")
print(result.session.access_token)