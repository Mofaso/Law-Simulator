
import datetime
from datetime import timezone, timedelta

# Define IST as in app.py
IST = timezone(timedelta(hours=5, minutes=30))

def test_admin_create_logic():
    print("--- Testing admin_create_user logic ---")
    # 1. Capture "Original Time" (Local)
    local_now = datetime.datetime.now()
    print(f"Local Wall Clock Time (Target): {local_now}")
    
    # 2. Simulate instantiation
    # Code in app.py uses: datetime.now(timezone.utc)
    stored_utc = datetime.datetime.now(timezone.utc)
    print(f"Stored Value (UTC): {stored_utc}")
    
    # 3. Simulate Retrieval & Display Logic
    c_at = stored_utc
    
    # Retrieve logic from admin_dashboard
    # PyMongo usually returns naive UTC if it stored UTC. 
    # But here we have an aware datetime object in memory. 
    # If we save to Mongo and read back, it becomes naive UTC.
    # Let's simulate that naive-ification that Mongo does.
    if c_at.tzinfo is not None:
        c_at_naive = c_at.replace(tzinfo=None) # This is what Mongo returns
    else:
        c_at_naive = c_at
        
    print(f"Retrieved from Mongo (Simulated Naive): {c_at_naive}")

    # Display Logic
    c_at_processed = c_at_naive
    if c_at_processed.tzinfo is None:
        c_at_processed = c_at_processed.replace(tzinfo=timezone.utc)
    
    final_ist = c_at_processed.astimezone(IST)
    print(f"Displayed Time (IST): {final_ist}")
    print(f"Formatted: {final_ist.strftime('%Y-%m-%d %H:%M')}")
    
    diff = final_ist.replace(tzinfo=None) - local_now.replace(tzinfo=None)
    print(f"Difference (Displayed - Local): {diff}")

def test_auto_create_logic():
    print("\n--- Testing auto_create_initial_admin logic (Naive) ---")
    # 1. Local time
    local_now = datetime.datetime.now()
    
    # 2. Instantiate Naive
    stored_naive = datetime.datetime.now() # User's local time, but naive
    print(f"Stored Value (Naive Local): {stored_naive}")
    
    # 3. Retrieval
    # If I store naive (12:00) into Mongo, Mongo assumes it's UTC.
    # So it stores it as 12:00 UTC.
    # When I retrieve it, I get 12:00 (Naive).
    c_at_naive = stored_naive 
    
    # 4. Display Logic
    c_at_processed = c_at_naive
    if c_at_processed.tzinfo is None:
        c_at_processed = c_at_processed.replace(tzinfo=timezone.utc) # Treats 12:00 as 12:00 UTC
        
    final_ist = c_at_processed.astimezone(IST) # Converts 12:00 UTC to 17:30 IST
    
    print(f"Displayed Time (IST): {final_ist}")
    print(f"Formatted: {final_ist.strftime('%Y-%m-%d %H:%M')}")
    
    diff = final_ist.replace(tzinfo=None) - local_now
    print(f"Difference (Displayed - Local): {diff}")

if __name__ == "__main__":
    test_admin_create_logic()
    test_auto_create_logic()
