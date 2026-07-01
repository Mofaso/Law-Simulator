import google.generativeai as genai

# ✅ Add this line to manually pass your key
genai.configure(api_key="AIzaSyC94LAHrH-FDmsG4KRJZHJ2wbh49yEjVGY")

print("🔍 Fetching available Gemini models...\n")

for model in genai.list_models():
    print(f"- {model.name}")
