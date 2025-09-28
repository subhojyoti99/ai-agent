from fastapi import FastAPI, Request, Form
from fastapi.responses import Response, StreamingResponse
from fastapi.staticfiles import StaticFiles
from twilio.twiml.voice_response import VoiceResponse, Gather
from fastapi.middleware.cors import CORSMiddleware
import requests
import os
import json
import asyncio
from twilio.rest import Client
from dotenv import load_dotenv
import uvicorn

load_dotenv()

app = FastAPI()

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

account_sid = os.getenv("TWILIO_ACCOUNT_SID")
print("account sid 11 ", account_sid)
auth_token = os.getenv("TWILIO_AUTH_TOKEN")
print("auth_token 33 ", auth_token)
TWILIO_PHONE_NUMBER = os.getenv("TWILIO_PHONE_NUMBER")
print("TWILIO_PHONE_NUMBER 44 ", TWILIO_PHONE_NUMBER)
conversation_histories = {}

client = Client(account_sid, auth_token)
print("client 55 ", client)
GROQ_API_KEY = os.getenv("GROQ_API_KEY")
print("GROQ_API_KEY 66 ", GROQ_API_KEY)

@app.get("/")
def root():
    return {"message": "AI Call Agent Ready"}

def is_sentence_boundary(text):
    return text.strip().endswith((".", "!", "?"))

@app.post("/chat")
async def chat(message: str = Form(...)):
    print("Inside the /chat")

    headers = {
        "Authorization": f"Bearer {GROQ_API_KEY}",
        "Content-Type": "application/json"
    }

    payload = {
        "model": "llama-3.1-8b-instant",
        "messages": [
            {"role": "system", "content": "You are a helpful assistant."},
            {"role": "user", "content": message}
        ]
    }

    response = requests.post(
        "https://api.groq.com/openai/v1/chat/completions",
        headers=headers,
        json=payload
    )

    print("Response ", response)

    if response.status_code != 200:
        return {"error": response.text}

    result = response.json()
    return {
        "reply": result["choices"][0]["message"]["content"]
    }

@app.post("/inbound-agent")
async def inbound_handler(request: Request):
    """
    First interaction (no SpeechResult): Greets caller and redirects back to endpoint.
    If caller says thanks: Responds politely and hangs up.
    Otherwise: Saves input, queries Groq API, streams reply, and redirects for continuation.
    Args:
        request (Request): Twilio form data with SpeechResult (caller input) and CallSid (unique call ID).
    Returns:
        Response: TwiML XML telling Twilio to play, gather, hang up, or redirect.
    """
    print("=== INBOUND CALL RECEIVED ===")  # Enhanced logging
    print(f"Request method: {request.method}")
    print(f"Request URL: {request.url}")
    print(f"Request headers: {dict(request.headers)}")
    
    form = await request.form()
    print(f"Form data received: {dict(form)}")  # Log all form data
    
    speech_result = form.get("SpeechResult")
    call_sid = form.get("CallSid")

    print("call_sid 77 ", call_sid)
    print("speech_result: ", speech_result)
    
    # Conversation memory per call
    if call_sid not in conversation_histories:
        conversation_histories[call_sid] = [
            {
                "role": "system", 
                "content": """
                    You are a visa assistant.
                    Your goal is to determine the most suitable visa type for the user.
                    You must follow these rules:

                    1. Ask a maximum of **three to four questions** (about nationality, requesting country, purpose of visit, and duration/occupation if relevant).
                    2. Keep questions short, clear, and conversational.
                    3. After the third question, based on all collected answers, **suggest the most appropriate visa type and Category suggestion like H-1B, F-1/J-1**.
                    4. If you already have enough information before 3-4 questions, you can suggest the visa earlier.
                    5. Do not ask unnecessary follow-up questions after giving the visa recommendation.
                    Do not need to explaine, just ask questions that you can find the visa type.
                """
            }
        ]
    
    conversation_history = conversation_histories[call_sid]
    
    response = VoiceResponse()

    print("TwiML response object created: ", response)
    
    gather = Gather(
        input="speech",
        action="/inbound-agent",
        method="POST",
        speechTimeout="2",
        speechModel="googlev2_long",
        hints="Listen carefully for names."
    )
    
    thank_keywords = ["thank", "thanks", "thank you", "thank u"]
    
    if not speech_result:
        # First interaction - welcome message
        print("First interaction - sending welcome message")
        gather.say("Hello! Welcome to the Visa Assistant. How can I help you today?")
        response.append(gather)
        response.redirect("https://<domain>/inbound-agent")
        print(f"Generated TwiML: {str(response)}")
        return Response(content=str(response), media_type="application/xml")
    
    if any(word in speech_result.lower() for word in thank_keywords):
        print("Thank you detected - hanging up")
        response.say("You're welcome! Goodbye!")
        response.hangup()
        return Response(content=str(response), media_type="application/xml")

    # Save user input to conversation history
    conversation_history.append({"role": "user", "content": speech_result})
    print(f"Added user message to history: {speech_result}")
    
    buffer = ""
    try:
        print("Making request to Groq API...")
        with requests.post(
            "https://api.groq.com/openai/v1/chat/completions",
            headers={"Authorization": f"Bearer {GROQ_API_KEY}"},
            json={
                "model": "llama-3.1-8b-instant",
                "messages": conversation_history[-10:],
                "temperature": 0.2,
                "max_tokens": 150,
                "stream": True,
            },
            stream=True,
        ) as r:
            for line in r.iter_lines():
                if not line:
                    continue
                
                line_str = line.decode()
                if line_str.startswith("data: "):
                    line_str = line_str[6:]
                
                if line_str.strip() == "[DONE]":
                    break
                
                try:
                    data = json.loads(line_str)
                    chunk = data.get("choices", [{}])[0].get("delta", {}).get("content", "")
                    if chunk:
                        buffer += chunk
                    
                    if is_sentence_boundary(buffer):
                        # Save assistant response to conversation history
                        conversation_history.append({"role": "assistant", "content": buffer.strip()})
                        gather.say(buffer.strip())
                        response.append(gather)
                        buffer = ""
                        
                except json.JSONDecodeError as e:
                    print(f"JSON decode error: {e}")
                    continue
        
        # Flush any remaining text in buffer
        if buffer.strip():
            conversation_history.append({"role": "assistant", "content": buffer.strip()})
            gather.say(buffer.strip())
            response.append(gather)
            
    except Exception as e:
        print(f"Groq API error: {e}")
        gather.say("I'm sorry, I'm having trouble connecting. Could you please try again?")
        response.append(gather)
    
    response.redirect("https://<domain>/inbound-agent")
    print(f"Final TwiML response: {str(response)}")
    return Response(content=str(response), media_type="application/xml")

# Add a health check endpoint for debugging
@app.get("/health")
def health_check():
    return {"status": "healthy", "message": "Server is running"}

if __name__ == "__main__":
    print("Starting AI Agent!")
    uvicorn.run("voice_agent:app", host="0.0.0.0", port=9030)
