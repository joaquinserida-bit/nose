from flask import Flask, request, jsonify

app = Flask(__name__)

@app.route("/")
def home():
    # Chatbot frontend en HTML
    return """
    <!DOCTYPE html>
    <html>
    <head>
        <meta charset="utf-8">
        <title>Chatbot Médico</title>
        <style>
            body { font-family: Arial, sans-serif; background:#f9f9f9; }
            #chat-box {
                height: 300px;
                overflow-y: auto;
                border: 1px solid #ccc;
                border-radius: 8px;
                padding: 10px;
                background: #fff;
                margin-bottom: 10px;
            }
            .user { color: blue; margin: 5px 0; }
            .bot { color: green; margin: 5px 0; }
        </style>
    </head>
    <body>
        <h2>🤖 Chatbot Médico</h2>
        <div id="chat-box"></div>
        <input id="user-input" type="text" placeholder="Escribe tu mensaje..." style="width:70%;padding:5px;">
        <button onclick="sendMessage()">Enviar</button>

        <script>
        async function sendMessage() {
            const input = document.getElementById("user-input");
            const message = input.value;
            if (!message) return;

            const chatBox = document.getElementById("chat-box");
            chatBox.innerHTML += `<div class='user'><b>Tú:</b> ${message}</div>`;
            input.value = "";

            try {
                const res = await fetch("/chat", {
                    method: "POST",
                    headers: {"Content-Type": "application/json"},
                    body: JSON.stringify({message})
                });
                const data = await res.json();
                chatBox.innerHTML += `<div class='bot'><b>Bot:</b> ${data.response}</div>`;
                chatBox.scrollTop = chatBox.scrollHeight;
            } catch (err) {
                chatBox.innerHTML += `<div style='color:red;'><b>Error:</b> No se pudo conectar al servidor.</div>`;
            }
        }
        </script>
    </body>
    </html>
    """

@app.route("/chat", methods=["POST"])
def chat():
    data = request.get_json()
    user_message = data.get("message", "")

    # Respuesta básica
    if "cáncer" in user_message.lower():
        respuesta = "Puedo ayudarte con información general sobre síntomas y prevención del cáncer. ¿Qué deseas saber en específico?"
    else:
        respuesta = "Soy un asistente médico. Pregúntame sobre síntomas relacionados con el cáncer."

    return jsonify({"response": respuesta})

if __name__ == "__main__":
    import os
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port)
