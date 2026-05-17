import os
print("=== ENV DEBUG ===")
print("COOKIE_ENC_KEY present:", "COOKIE_ENC_KEY" in os.environ)
print("COOKIE_ENC_KEY length:", len(os.environ.get("COOKIE_ENC_KEY", "")))
