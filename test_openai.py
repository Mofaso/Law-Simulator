import google.generativeai as genai

genai.configure(api_key="YOUR_GOOGLE_API_KEY")

model = genai.GenerativeModel("gemini-1.5-flash-latest")

response = model.generate_content("Explain cyber law in simple terms.")
print(response.text)
