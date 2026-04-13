import os

def run_all_tests():
    for root, dirs, files in os.walk("tests"):
        for file in files:
            if file.startswith("test_") and file.endswith(".py"):
                path = os.path.join(root, file)
                print(f"Running {path}")
                os.system(f"python {path}")

if __name__ == "__main__":
    run_all_tests()