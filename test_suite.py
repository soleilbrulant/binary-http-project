import subprocess
import time
import os

def run_test(name, command):
    print(f"Running Test: {name}...", end=" ")
    try:
        result = subprocess.run(command, shell=True, capture_output=True, text=True, timeout=10)
        if result.returncode == 0:
            print("✅ PASS")
            return True
        else:
            print(f"❌ FAIL (Exit Code: {result.returncode})")
            return False
    except Exception as e:
        print(f"❌ ERROR: {e}")
        return False

def main():
    print("====================================================")
    print(" B-HTTP Protocol Automated Test Suite")
    print("====================================================\n")

    # 1. Start server in background
    print("[*] Starting server in background...")
    server_proc = subprocess.Popen(["python3", "bserve.py", "./www", "9000"],
                                   stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    time.sleep(1) # Let server start

    tests = [
        ("Happy Path (index.html)", "python3 bcurl.py localhost:9000/index.html"),
        ("404 Handling (missing.html)", "python3 bcurl.py localhost:9000/missing.html"), # Expect failure
    ]

    results = []

    # Test Happy Path
    results.append(run_test("Happy Path (index.html)", "python3 bcurl.py localhost:9000/index.html"))

    # Test 404 (Special case: should return exit code 1)
    print("Running Test: 404 Handling...", end=" ")
    res = subprocess.run("python3 bcurl.py localhost:9000/missing.html", shell=True, capture_output=True)
    if res.returncode == 1:
        print("✅ PASS (Correctly exited with 1)")
        results.append(True)
    else:
        print(f"❌ FAIL (Expected exit 1, got {res.returncode})")
        results.append(False)

    # Test Verbose Mode
    results.append(run_test("Verbose Mode", "python3 bcurl.py -v localhost:9000/index.html"))

    # Cleanup
    server_proc.terminate()

    print("\n====================================================")
    success_count = sum(results)
    print(f"FINAL RESULT: {success_count}/{len(results)} Tests Passed")
    print("====================================================")

    if success_count == len(results):
        print("\nOVERALL VERDICT: SYSTEM STABLE ✅")
    else:
        print("\nOVERALL VERDICT: ISSUES DETECTED ❌")

if __name__ == "__main__":
    main()
