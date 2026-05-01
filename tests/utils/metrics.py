import json
import matplotlib.pyplot as plt

def plot_success_rate():
    with open("test_results/results.json") as f:
        data = json.load(f)

    total = len(data)
    passed = sum(1 for d in data if d["status"] == "PASS")
    failed = total - passed

    labels = ["PASS", "FAIL"]
    values = [passed, failed]

    plt.bar(labels, values)
    plt.title("Test Success Rate")
    plt.xlabel("Result")
    plt.ylabel("Count")

    plt.savefig("test_results/success_rate.png")
    plt.show()