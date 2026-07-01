# test_perspectives.py
# Run this file to verify your simulator generates DIFFERENT perspectives.

from app import (
    generate_dynamic_impact_analysis_cached,
    detect_domain_cached,
    sentiment_score_cached
)

TEST_LAW = """
The government proposes a new regulation imposing penalties for misuse of personal data
and increasing compliance requirements for technology companies.
The law also introduces a small fee for data processing services.
"""

print("\n==============================")
print("AI LAW SIMULATOR — UNIT TEST")
print("==============================\n")

print("Input Law Text:")
print(TEST_LAW)
print("\n----------------------------------")
print("Running dynamic impact analysis...")
print("----------------------------------\n")

# Run the dynamic impact engine
result = generate_dynamic_impact_analysis_cached(TEST_LAW)

print(f"Detected Domain: {result['domain']}")
print(f"Base Sentiment Score: {sentiment_score_cached(TEST_LAW)}\n")

print("Generated Groups (Profiles):")
for g in result["profile"]:
    print(" -", g)

print("\n----------------------------------")
print("Group-wise Perspective Analysis")
print("----------------------------------\n")

impacts = result["impacts"]

for group, details in impacts.items():
    print(f"GROUP: {group}")
    print(f"  Effect Label: {details['label']}")
    print(f"  Score: {details['score']}")
    print(f"  Explanation: {details['explanation']}")
    print("")

print("==============================")
print("TEST COMPLETE")
print("==============================\n")
