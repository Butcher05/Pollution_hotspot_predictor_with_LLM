import ollama

def is_environment_question(question):

    response = ollama.chat(
        model="ecogpt",
        messages=[
            {
                "role": "system",
                "content": """
You are a classifier.

Determine whether the user's question is related to:

- Environment
- Pollution
- AQI
- Air quality
- Climate change
- Sustainability
- Renewable energy
- Biodiversity
- Nature
- Wildlife
- Conservation
- Environmental health
- Green technology
- Smart cities
- Environmental policies
- Environmental data
- Environmental AI
- Pollution hotspot prediction

Reply with ONLY:

YES

or

NO
"""
            },
            {
                "role": "user",
                "content": question
            }
        ]
    )

    result = response["message"]["content"].strip().upper()

    return result == "YES"