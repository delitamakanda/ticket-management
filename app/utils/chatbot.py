import openai
from flask import current_app
from ..models import Ticket

def generate_chatbot_response(user_input):
    openai.api_key = current_app['OPENAI_API_KEY']
    
    relevant_tickets = Ticket.query.filter(Ticket.description.ilike(f"%{user_input}%")).limit(5).all()
    relevant_ticket_titles = "\n".join([f"-{t.title}: {t.description}" for t in relevant_tickets])
    
    prompt = f"""
    You are a helpful AI assistant for a ticketing system. Help users by answering questions before they create a new support ticket.
    
    User Question: {user_input}
    
    Here are some relevant tickets that might help:
    {relevant_ticket_titles if relevant_ticket_titles else "No relevant tickets found."}
    
    Provide a concise and helpful response to the user. If you cannot resolve the issue, suggest creating a ticket.
    """
    
    response = openai.Completion.create(
        engine="gpt-4o-mini",
        prompt=[{"role": "user", "content": prompt}],
        max_tokens=300,
        temperature=0.7,
    )
    
    return response.choices[0].message.content.strip()