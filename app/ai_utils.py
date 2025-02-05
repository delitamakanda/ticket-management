import openai
from flask import current_app

def generate_ticket_suggestion(user_input):
    openai.api_key = current_app['OPENAI_API_KEY']
    
    prompt = f"""
    The user is requesting a new support ticket with the following description: {user_input}.
    
    Generate a detailed title for the ticket, considering the following points:
    - Clear and concise **title**
    - A well-defined **priority** (low, medium, high)
    - A **status** (open, closed, in_progress)
    - A **description** that accurately explains the issue and request
    """
    
    response = openai.Completion.create(
        engine="gpt-4",
        prompt=[{"role": "user", "content": prompt}],
        max_tokens=100,
        temperature=0.7,
    )
    
    ai_response = response.choices[0]["message"]["content"].strip()
    title, priority, status, description = ai_response.split("\n", 1)
    
    return title, priority, status, description.strip()
