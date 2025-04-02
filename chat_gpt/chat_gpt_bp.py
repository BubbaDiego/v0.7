import os
import logging
from flask import Blueprint, render_template, request, jsonify
from openai import OpenAI
from dotenv import load_dotenv

# Load environment variables from .env file
load_dotenv()

# Set up logging for debugging
logger = logging.getLogger(__name__)
logger.setLevel(logging.DEBUG)

# Instantiate the OpenAI client using the API key
client = OpenAI(api_key=os.getenv("OPEN_AI_KEY"))

# Create the blueprint for ChatGPT
chat_gpt_bp = Blueprint('chat_gpt_bp', __name__, template_folder='templates')

@chat_gpt_bp.route('/chat', methods=['GET'])
def chat():
    logger.debug("GET /chat - Rendering chat interface.")
    return render_template('chat_gpt.html')

@chat_gpt_bp.route('/chat', methods=['POST'])
def chat_post():
    logger.debug("POST /chat - Received request.")

    data = request.get_json()
    logger.debug(f"Request JSON: {data}")

    user_message = data.get('message', '').strip()
    logger.debug(f"User message: '{user_message}'")

    if not user_message:
        logger.debug("No valid message provided; returning error response.")
        return jsonify({"reply": "Please provide a valid message."}), 400

    messages = [
        {"role": "system", "content": "You are a helpful assistant."},
        {"role": "user", "content": user_message}
    ]
    logger.debug(f"Sending messages to OpenAI: {messages}")

    try:
        response = client.chat.completions.create(
            model="gpt-3.5-turbo",
            messages=messages
        )
        logger.debug("Received response from OpenAI API.")
        reply = response.choices[0].message.content.strip()
        logger.debug(f"ChatGPT reply: '{reply}'")
        return jsonify({"reply": reply})
    except Exception as e:
        import traceback
        error_trace = traceback.format_exc()
        logger.error(f"OpenAI API error: {e}\n{error_trace}")
        return jsonify({"reply": f"An error occurred: {e}"}), 500
