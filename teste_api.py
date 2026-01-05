import google.generativeai as genai
genai.configure(api_key="AIzaSyAmKniS7s6odyTWF1Pm9sV7FJtQbG3xFnc")
modelo = genai.GenerativeModel("gemini-1.5-flash")
resp = modelo.generate_content("Diga 'Olá' em JSON: {\"msg\":\"Olá\"}")
print(resp.text)
