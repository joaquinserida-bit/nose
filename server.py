Chatbot médico base — server.py
Proyecto: Chatbot que utiliza una base local de datos médica (síntomas) y, opcionalmente,
la API de OpenAI para generar respuestas realistas y empáticas.

Características:
- Flask app exportando la variable `app` (necesaria para Render/gunicorn).
- Carga un archivo JSON local `symptoms_db.json` con información médica estructurada.
- Endpoint `/chat` para interacción del paciente.
- Endpoint `/ingest` para añadir/actualizar entradas médicas (protegido mediante API key simple).
- Si la variable de entorno `OPENAI_API_KEY` está presente, usa la API de OpenAI (chat completions).
  Si no, responde con un motor de respuestas basado en reglas + extracción de la base local.
- Mensajes empáticos y descargos de responsabilidad (no sustituye diagnóstico profesional).

Instrucciones de despliegue (Render / Heroku / VPS):
- Asegúrate de que `OPENAI_API_KEY` esté en las variables de entorno si quieres usar OpenAI.
- Comando de inicio en Render (si mantienes este archivo con nombre server.py):
    gunicorn server:app

Requisitos (requirements.txt mínimo):
flask
openai
python-dotenv
gunicorn

NOTA DE SEGURIDAD: Este servicio provee información general y no debe reemplazar atención médica.
"""

import os
import json
import difflib
from flask import Flask, request, jsonify, abort
from datetime import datetime

# Intent: nombrar la app exactamente como espera Render/Gunicorn
app = Flask(__name__)

# Config
DATA_FILE = os.environ.get("SYMPTOMS_DB", "symptoms_db.json")
INGEST_KEY = os.environ.get("INGEST_KEY", "changeme_ingest_key")  # proteger endpoint /ingest
OPENAI_KEY = os.environ.get("OPENAI_API_KEY")

# Try to import OpenAI only if key is present
openai = None
if OPENAI_KEY:
    try:
        import openai
        openai.api_key = OPENAI_KEY
    except Exception:
        openai = None


# ------------------------- Helpers -------------------------

def ensure_data_file():
    """Creates a starter symptoms DB if none exists."""
    if not os.path.exists(DATA_FILE):
        starter = {
            "cancer_general": {
                "title": "Información general sobre el cáncer",
                "description": "El cáncer es un conjunto de enfermedades caracterizadas por un crecimiento celular anormal. Los síntomas varían según el tipo y la etapa.",
                "common_symptoms": [
                    "fatiga inusual",
                    "pérdida de peso inexplicada",
                    "dolor persistente",
                    "bultos o masas palpables",
                    "cambios en la piel",
                    "sangrado anormal"
                ],
                "notes": "Esta entrada es informativa — no substituye la opinión de un profesional de la salud."
            },
            "breast_cancer": {
                "title": "Cáncer de mama",
                "description": "Síntomas frecuentes de cáncer de mama incluyen bultos en la mama, cambios en la piel de la mama o secreción por el pezón.",
                "common_symptoms": ["bulto en la mama","cambios en la piel de la mama","secreción por el pezón","dolor mamario persistente"],
                "notes": "Ante la aparición de cualquier bulto o cambio, consulte a un profesional cuanto antes."
            },
            "lung_cancer": {
                "title": "Cáncer de pulmón",
                "description": "Síntomas pueden incluir tos persistente, sangre al toser, dificultad para respirar y dolor torácico.",
                "common_symptoms": ["tos persistente","hemoptisis (sangre al toser)","dificultad para respirar","dolor torácico"],
                "notes": "Fumar y exposición a ciertos carcinógenos aumentan el riesgo."
            }
        }
        with open(DATA_FILE, "w", encoding="utf-8") as f:
            json.dump(starter, f, ensure_ascii=False, indent=2)


def load_symptoms_db():
    ensure_data_file()
    with open(DATA_FILE, "r", encoding="utf-8") as f:
        return json.load(f)


def save_symptoms_db(db):
    with open(DATA_FILE, "w", encoding="utf-8") as f:
        json.dump(db, f, ensure_ascii=False, indent=2)


def find_relevant_entries(message, db, n=3):
    """Busca coincidencias por palabras clave aproximadamente usando difflib en títulos y síntomas."""
    message_lower = message.lower()
    candidates = []
    # Build a list of searchable texts
    for key, entry in db.items():
        search_text = (entry.get("title", "") + " " + entry.get("description", "") + " " + " ".join(entry.get("common_symptoms", []))).lower()
        # ratio of match using difflib
        ratio = difflib.SequenceMatcher(a=message_lower, b=search_text).quick_ratio()
        # also check word overlap
        words = set([w.strip(".,;:()[]") for w in message_lower.split() if len(w) > 2])
        overlap = sum(1 for w in words if w in search_text)
        score = ratio + 0.1 * overlap
        candidates.append((score, key, entry))

    candidates.sort(key=lambda x: x[0], reverse=True)
    return [c for _, _, c in candidates[:n] if _ > 0 or c.get('common_symptoms')]


# ------------------------- Routes -------------------------

@app.route("/", methods=["GET"])
def status():
    return jsonify({
        "status": "ok",
        "service": "Chatbot médico - base local",
        "time": datetime.utcnow().isoformat() + "Z"
    })


@app.route("/chat", methods=["POST"])
def chat():
    payload = request.get_json(force=True)
    if not payload:
        return jsonify({"error": "No JSON payload provided"}), 400

    message = payload.get("message", "").strip()
    patient_info = payload.get("patient_info", {})  # opcional: edad, sexo, history

    if not message:
        return jsonify({"error": "El campo 'message' es requerido."}), 400

    db = load_symptoms_db()
    relevant = find_relevant_entries(message, db)

    # Build context for a model or rule-based responder
    context_parts = []
    if relevant:
        for r in relevant:
            context_parts.append(f"- {r.get('title')}: {r.get('description')} Síntomas comunes: {', '.join(r.get('common_symptoms', []))}.")
    else:
        context_parts.append("No se encontraron coincidencias directas en la base de síntomas locales.")

    context_text = "\n".join(context_parts)

    # Safety disclaimer prefix
    disclaimer = (
        "Nota: soy un asistente informativo y no un sustituto de un profesional médico. "
        "Si tienes una emergencia, busca atención médica inmediata o llama a los servicios de emergencia locales.\n\n"
    )

    # If OpenAI is configured, use it to produce a more humanoid, empático y detallado texto
    if openai:
        try:
            system_prompt = (
                "Eres un asistente médico empático y claro. Proporciona información general basada en los datos entregados, "
                "explica síntomas relevantes, sugiere cuándo consultar a un profesional y ofrece pasos prácticos y calmados. "
                "Nunca des un diagnóstico definitivo; siempre incluye un recordatorio para buscar atención médica."
            )

            user_prompt = (
                f"Contexto médico local:\n{context_text}\n\n"
                f"Información del paciente: {json.dumps(patient_info, ensure_ascii=False)}\n\n"
                f"Pregunta del paciente: {message}\n\n"
                "Responde en español con tono empático, claro y práctico. Primero resume brevemente la preocupación, luego explica posibles causas o síntomas relacionados, "
                "y cierra con pasos recomendados y cuándo acudir a urgencias."
            )

            completion = openai.ChatCompletion.create(
                model=os.environ.get("OPENAI_MODEL", "gpt-4o-mini"),
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_prompt}
                ],
                max_tokens=600,
                temperature=0.2
            )

            answer = completion.choices[0].message.content.strip()
            full_answer = disclaimer + answer

            return jsonify({"response": full_answer, "source": "openai", "matched_entries": [r.get('title') for r in relevant]})

        except Exception as e:
            # Fall back to rule-based if OpenAI call falla
            app.logger.exception("OpenAI request failed: %s", e)

    # Rule-based responder (fallback)
    summary = "Resumen: He encontrado la siguiente información que podría estar relacionada con tu mensaje:\n" + context_text
    suggestions = (
        "Pasos sugeridos:\n"
        "1) Observa la evolución de los síntomas durante 48-72 horas.\n"
        "2) Si aparecen signos de alarma (fiebre alta, dificultad para respirar, sangrado abundante, pérdida rápida de peso, dolor intenso), busca atención de urgencias.\n"
        "3) Programa una consulta con un profesional de la salud para evaluación y pruebas complementarias.\n"
        "4) Lleva un registro de síntomas: fecha, hora, intensidad y posibles desencadenantes.\n"
    )

    empathetic_close = "Si quieres, dime más detalles (edad, cuánto tiempo hace, si tienes antecedentes) y te doy una guía más precisa sobre qué preguntar al médico."

    response_text = disclaimer + summary + "\n" + suggestions + "\n" + empathetic_close

    return jsonify({"response": response_text, "source": "local_db", "matched_entries": [r.get('title') for r in relevant]})


@app.route("/ingest", methods=["POST"])
def ingest():
    """Permite agregar o actualizar entradas en la base local. Protegido por INGEST_KEY simple."""
    key = request.headers.get("X-INGEST-KEY", "")
    if key != INGEST_KEY:
        return jsonify({"error": "Unauthorized"}), 401

    payload = request.get_json(force=True)
    if not payload or not isinstance(payload, dict):
        return jsonify({"error": "Payload inválido; se espera un dict JSON con clave -> entry."}), 400

    db = load_symptoms_db()
    db.update(payload)
    save_symptoms_db(db)

    return jsonify({"status": "ok", "updated_keys": list(payload.keys())})


# ------------------------- Error handlers -------------------------

@app.errorhandler(500)
def handle_500(e):
    app.logger.exception("Server error: %s", e)
    return jsonify({"error": "Internal server error"}), 500


# ------------------------- Run -------------------------
if __name__ == "__main__":
    # Default development run (no gunicorn)
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port, debug=os.environ.get("FLASK_DEBUG", "false").lower() == "true")
