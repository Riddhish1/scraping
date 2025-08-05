import json

# Load the original file
with open('all_schemes_data.json', 'r', encoding='utf-8') as f:
    data = json.load(f)

print(f"Original file has {len(data)} entries")

# Remove duplicates based on link
seen_links = set()
unique_schemes = []

for scheme in data:
    link = scheme["link"]
    if link not in seen_links:
        seen_links.add(link)
        unique_schemes.append(scheme)

print(f"After removing duplicates: {len(unique_schemes)} unique schemes")

# Save the cleaned data
with open('cleaned_schemes_data.json', 'w', encoding='utf-8') as f:
    json.dump(unique_schemes, f, indent=2, ensure_ascii=False)

print("Saved cleaned data to 'cleaned_schemes_data.json'")
