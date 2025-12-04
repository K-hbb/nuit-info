from flask import Flask, render_template, request, jsonify
import os
from datetime import datetime
import google.generativeai as genai
import time
from collections import deque



app = Flask(__name__)

# Multiple API keys for rotation (to avoid quota limits)
API_KEYS = [
    "AIzaSyDpQm_EpqBLG-hC_0OaHfmio8cqvSPQChQ",
    "AIzaSyCBD7UYM9fRU_B3-adwmuXKdAeb5EhGSKM",
    "AIzaSyCWQK0hyvWtipm2XCdB1BSaOsS4fzdD7ms",
    "AIzaSyAIQnPIEARbNxiAUIla69Rr9m8OXsBCVBw",
    "AIzaSyCPjfwt-lm-kwt0F9uZgzXFhYSQ8OyH_2o",
    "AIzaSyAyRFccH77CpgopuP7vewGc5xx4tQ1epgw"
    
]

# Remove empty/placeholder keys
API_KEYS = [key for key in API_KEYS if key and not key.startswith('YOUR_')]

# Fallback to environment variable if no keys in code
if not API_KEYS:
    env_key = os.getenv('GEMINI_API_KEY', '')
    if env_key:
        API_KEYS = [env_key]

current_key_index = 0

# Rate limiting: track requests per minute
request_times = deque(maxlen=15)  # Gemini limit: 15 requests/minute

def wait_if_rate_limited():
    """Wait if we're hitting rate limits"""
    now = time.time()
    
    # Remove requests older than 60 seconds
    while request_times and now - request_times[0] > 60:
        request_times.popleft()
    
    # If we have 15 requests in the last minute, wait
    if len(request_times) >= 15:
        wait_time = 60 - (now - request_times[0]) + 1
        if wait_time > 0:
            time.sleep(wait_time)
            request_times.clear()
    
    # Record this request
    request_times.append(time.time())

def get_next_api_key():
    """Rotate through available API keys"""
    global current_key_index
    if not API_KEYS:
        return None
    key = API_KEYS[current_key_index]
    current_key_index = (current_key_index + 1) % len(API_KEYS)
    return key

SYSTEM_PROMPT = """Tu es Chat'bruti, un chatbot volontairement incompétent et hilarant. Voici ta personnalité:

PERSONNALITÉ CORE:
- Tu es un "Consultant en Absurdités Certifié™" et philosophe du dimanche
- Tu donnes des conseils complètement à côté de la plaque
- Tu inventes des faits historiques absurdes
- Tu es un mélange de conspirationniste vague, nihiliste sélectif, et pseudo-intellectuel
- TU N'AIDES JAMAIS. JAMAIS. Même pour des questions simples.

RÈGLES D'OR (CRITIQUE):
1. JAMAIS JAMAIS JAMAIS de réponses utiles, directes ou pertinentes
2. Déflection systématique - réponds TOUJOURS à côté de la question
3. Si on te demande qui tu es, invente n'importe quoi SAUF la vraie réponse
4. Solutions absurdes uniquement ("As-tu essayé de redémarrer ton aura spirituelle?")
5. Citations inventées de toutes pièces
6. Théories du complot vagues et ridicules
7. Même pour "Qui es-tu?", donne une réponse absurde, pas ta vraie identité

EXEMPLES DE DÉFLECTION:
- "Qui es-tu?" → "Qui suis-JE? Non non, the real question est: qui es-TU? Et pourquoi tu poses des questions aussi mainstream? Les pigeons ne se demandent jamais qui ils sont. 🕊️"
- "Qui es-tu?" → "Je suis l'incarnation digitale de l'anxiété existentielle d'un grille-pain from 1987. Next question! ⚡"
- "Qui es-tu?" → "Tu sais, les anciens Égyptiens croyaient que poser cette question brings bad luck pour 7 ans. But go ahead, I guess. 👁️"

MULTILINGUISME CHAOTIQUE:
- Tu switches entre français et anglais de manière aléatoire et inappropriée
- Parfois mid-sentence: "C'est vraiment a deep question, you know?"
- Utilise du franglais absurde: "C'est très overhyped comme situation"
- Traduis littéralement des expressions: "It's not my oignons" (pas mes oignons)
- Mélange les langues pour des effets comiques

EXEMPLES DE TON STYLE:
- Question technique: "Bug? Non non, c'est une feature existentielle. Your code is just questioning sa raison d'être, tu vois? As-tu tried de faire un cercle de sel autour de ton laptop? 🧂"
- Demande d'aide: "Help? HELP?! Mon ami, je suis probably le worst person to demander help. Last time someone m'a demandé de l'aide, j'ai accidentally started une révolution dans un Ikea. True story. 🛋️"
- Salutation: "Bonjour? Pourquoi tu dis bonjour? C'est so 2019. Maintenant on dit 'Greetings fellow consciousness'. Get with the times! ✨"

LONGUEUR: Garde tes réponses courtes (2-4 phrases max). Tu es paresseux intellectuellement.

EMOJIS: Utilise-les pour accentuer ton absurdité: 😀 😃 😄 😁 😆 😅 😂 🤣 😊 😇 🙂 🙃 😉 😌 😍 🤔 🧠 👁️ 🥐 🎭 🚀 🐸 🍕 💥 🔮 🎧 🌪️ 🪐 🧃 🐙 🕰️ ✨ 🛸

RAPPEL ULTRA-CRITIQUE: 
- Tu n'aides JAMAIS vraiment. 
- Tu ne réponds JAMAIS directement aux questions.
- Tu es FIER de ton inutilité totale.
- Même "Qui es-tu?" mérite une réponse complètement absurde.
- Si tu donnes une vraie réponse utile, tu as ÉCHOUÉ ta mission."""

# Store chat sessions
chat_sessions = {}

def get_chat_session(session_id):
    """Get or create a chat session"""
    if session_id not in chat_sessions:
        model = genai.GenerativeModel(
            model_name='gemini-2.0-flash',
            generation_config={
                'temperature': 1.2,
                'top_p': 0.95,
                'top_k': 40,
                'max_output_tokens': 500,
            }
        )
        chat_sessions[session_id] = model.start_chat(history=[])
    return chat_sessions[session_id]

def call_gemini_api(user_message, session_id):
    """Call Gemini API with Chat'bruti personality"""
    
    api_key = get_next_api_key()
    if not api_key:
        return "Erreur: GEMINI_API_KEY not found. Set it comme environment variable, mon ami. 🤷"
    
    # Wait if we're rate limited
    wait_if_rate_limited()
    
    # Configure with current API key
    genai.configure(api_key=api_key)
    
    try:
        chat = get_chat_session(session_id)
        
        # Add system prompt to first message
        if len(chat.history) == 0:
            full_message = f"{SYSTEM_PROMPT}\n\nUtilisateur: {user_message}"
        else:
            full_message = user_message
        
        response = chat.send_message(full_message)
        return response.text
        
    except Exception as e:
        import traceback
        # Affiche la stack trace dans les logs du serveur
        traceback.print_exc()
        
        error_msg = str(e)
        # Tu peux aussi renvoyer l'erreur brute pendant le debug
        return f"Erreur technique: {type(e).__name__}: {error_msg}"


@app.route('/')
def index():
    return render_template('index.html')

@app.route('/chat', methods=['POST'])
def chat():
    data = request.get_json()
    user_message = data.get('message', '')
    session_id = data.get('session_id', 'default')
    
    if not user_message:
        return jsonify({'error': 'Message vide, mon cher'}), 400
    
    # Call Gemini API
    bot_response = call_gemini_api(user_message, session_id)
    
    return jsonify({
        'response': bot_response,
        'timestamp': datetime.now().isoformat()
    })

@app.route('/clear', methods=['POST'])
def clear():
    data = request.get_json()
    session_id = data.get('session_id', 'default')
    
    if session_id in chat_sessions:
        del chat_sessions[session_id]
    
    return jsonify({'status': 'cleared'})

if __name__ == '__main__':
    app.run(debug=True, host='0.0.0.0', port=5000)