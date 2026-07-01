import google.generativeai as genai

# Paste the new key directly here for testing
genai.configure(api_key="AIzaSyBm113TWhF_DkUzrsxLm7cf_s0OrhAZE5o")

try:
    models = genai.list_models()
    for m in models:
        print(m.name, m.supported_generation_methods)
except Exception as e:
    print("❌ Error:", e)
