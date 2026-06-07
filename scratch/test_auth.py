"""Integration test for Multi-User Authentication."""
import requests
import json
import sys
import io

# Fix Windows console encoding for UTF-8
if sys.platform == 'win32':
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')
    sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding='utf-8', errors='replace')

BASE_URL = "http://127.0.0.1:5000"

def run_tests():
    print("=== STARTING AUTHENTICATION INTEGRATION TESTS ===")
    
    # 1. Test unauthenticated request
    print("\n[Test 1] Querying protected endpoint without token...")
    r = requests.get(f"{BASE_URL}/api/dashboard")
    if r.status_code == 401:
        print("✅ Correctly blocked! Status 401 Unauthorized.")
    else:
        print(f"❌ Failed! Expected 401, got {r.status_code}.")
        sys.exit(1)

    # 2. Test registration
    print("\n[Test 2] Registering a new test user...")
    test_user = {
        "username": f"test_user_{secrets_hex()}",
        "password": "testpassword123"
    }
    
    r = requests.post(f"{BASE_URL}/api/auth/register", json=test_user)
    if r.status_code == 200:
        data = r.json()
        token = data.get("token")
        print(f"✅ Registered successfully! Username: {test_user['username']}, Token: {token[:10]}...")
    else:
        print(f"❌ Failed to register! Code: {r.status_code}, Response: {r.text}")
        sys.exit(1)

    # 3. Test login
    print("\n[Test 3] Logging in with correct credentials...")
    r = requests.post(f"{BASE_URL}/api/auth/login", json=test_user)
    if r.status_code == 200:
        data = r.json()
        token = data.get("token")
        print(f"✅ Login successful! Token: {token[:10]}...")
    else:
        print(f"❌ Login failed! Code: {r.status_code}, Response: {r.text}")
        sys.exit(1)

    # 4. Test authenticated query
    print("\n[Test 4] Querying /api/auth/me with token...")
    r = requests.get(f"{BASE_URL}/api/auth/me", headers={"x-auth-token": token})
    if r.status_code == 200:
        data = r.json()
        print(f"✅ Successfully authenticated! Server returned username: {data.get('username')}")
        if data.get("username") != test_user["username"]:
            print("❌ Username mismatch!")
            sys.exit(1)
    else:
        print(f"❌ Authentication failed! Code: {r.status_code}, Response: {r.text}")
        sys.exit(1)

    # 5. Test querying dashboard with token
    print("\n[Test 5] Querying /api/dashboard with token...")
    r = requests.get(f"{BASE_URL}/api/dashboard", headers={"x-auth-token": token})
    if r.status_code == 200:
        data = r.json()
        print("✅ Successfully fetched dashboard stats. Flow state XP:", data.get("flow", {}).get("total_xp"))
    else:
        print(f"❌ Dashboard query failed! Code: {r.status_code}, Response: {r.text}")
        sys.exit(1)

    # 6. Test logout
    print("\n[Test 6] Logging out / revoking token...")
    r = requests.post(f"{BASE_URL}/api/auth/logout", headers={"x-auth-token": token})
    if r.status_code == 200:
        print("✅ Logged out successfully.")
    else:
        print(f"❌ Logout failed! Code: {r.status_code}, Response: {r.text}")
        sys.exit(1)

    # 7. Verify token is revoked
    print("\n[Test 7] Querying with revoked token...")
    r = requests.get(f"{BASE_URL}/api/auth/me", headers={"x-auth-token": token})
    if r.status_code == 401:
        print("✅ Correctly blocked revoked token! Status 401 Unauthorized.")
    else:
        print(f"❌ Failed! Expected 401 after logout, got {r.status_code}.")
        sys.exit(1)

    print("\n🎉 ALL AUTHENTICATION TESTS PASSED SUCCESSFULLY! 🎉")

def secrets_hex():
    import secrets
    return secrets.token_hex(4)

if __name__ == "__main__":
    run_tests()
