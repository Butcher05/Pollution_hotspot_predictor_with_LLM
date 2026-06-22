'''
import ollama

from chatbot.prompts import SYSTEM_PROMPT


def get_response(user_question):

    response = ollama.chat(

        model="llama3.2",

        messages=[

            {
                "role": "system",
                "content": SYSTEM_PROMPT
            },

            {
                "role": "user",
                "content": user_question
            }

        ]

    )

    return response["message"]["content"]
'''
import ollama

def get_response(question):

    try:

        response = ollama.chat(
            model="EcoGPT",
            messages=[
                {
                    "role":"user",
                    "content":question
                }
            ]
        )

        return response["message"]["content"]

    except Exception as e:

        return f"ERROR: {str(e)}"