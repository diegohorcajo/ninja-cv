# gemini_api.py

import json
import pprint
import re
from datetime import datetime
import fitz
from google.generativeai import GenerativeModel, configure

# === TEMPLATES ===
CV_TEMPLATE = {
    "education": [
        {
            "degree": str,
            "number": float,
            "field": str
        }
    ],
    "experience": [
        {
            "company": str,
            "roles": [
                {
                    "position": str,
                    "years": float
                }
            ],
            "total_years": float
        }
    ],
    "primary_sector": list,
    "soft_skills": list,
    "technical_abilities": list
}

OFFER_TEMPLATE = {
    "company": str,
    "education": {
        "field": str,
        "number": float,
        "min": str
    },
    "experience": {
        "max": float,
        "min": float
    },
    "role": str,
    "sector": str,
    "soft_skills": list,
    "technical_abilities": list
}

# === HELPERS ===

# leer cv
def read_cv(file_path: str) -> str:
    doc = fitz.open(file_path)
    cv = ""
    for page in doc:
        # devuelve bloques con coordenadas
        text = page.get_text("blocks")
        # Ordenar los bloques por (y, x) → para mantener coherencia de lectura
        blocks_sorted = sorted(text, key=lambda b: (b[1], b[0]))
        for b in blocks_sorted:
            cv += b[4]
        if len(cv) > 10000:
            return -1
        elif len(cv) < 10:
            return -2
    return cv


# parsear la respuesta de gemini
def fill_from_template(template, source):
    """
    Llena un diccionario siguiendo la estructura y tipos de 'template'
    usando los valores de 'source' solo si cumplen el tipo esperado.
    """
    if isinstance(template, dict):
        result = {}
        for key, expected in template.items():
            if key in source:
                result[key] = fill_from_template(expected, source[key])
            else:
                result[key] = None
        return result

    elif isinstance(template, list):
        if not isinstance(source, list):
            return []
        if not template:  # lista vacía como plantilla
            return source if isinstance(source, list) else []
        return [
            fill_from_template(template[0], item)
            for item in source if isinstance(item, dict)
        ]

    elif isinstance(template, type):
        if template is float and isinstance(source, (int, float)):
            return float(source)
        return source if isinstance(source, template) else None

    return None


def clean_and_validate_json(json_str: str) -> dict:
    """
    Clean and validate JSON string, fixing common formatting issues.
    
    Args:
        json_str: The JSON string to clean and validate
        
    Returns:
        dict: The parsed and cleaned JSON as a dictionary
        
    Raises:
        json.JSONDecodeError: If the JSON cannot be properly parsed after cleaning
    """
    if not json_str or not isinstance(json_str, str):
        raise ValueError("Input must be a non-empty string")
    
    # Remove trailing commas before closing brackets/braces
    json_str = re.sub(r',\s*([}\]])', r'\1', json_str)
    
    # Fix unescaped quotes within strings
    json_str = re.sub(r'(?<!\\)"(.*?)(?<!\\)"', 
                     lambda m: '"' + m.group(1).replace('"', '\\"') + '"', 
                     json_str)
    
    # Remove any non-printable characters
    json_str = ''.join(char for char in json_str if char.isprintable() or char.isspace())
    
    # Attempt to parse the cleaned JSON
    try:
        return json.loads(json_str)
    except json.JSONDecodeError as e:
        # If parsing still fails, try to extract JSON from the string
        match = re.search(r'({.*})', json_str, re.DOTALL)
        if match:
            try:
                return json.loads(match.group(1))
            except json.JSONDecodeError:
                pass
        raise json.JSONDecodeError("Failed to parse JSON after cleaning attempts", 
                                 json_str, e.pos) from e



class GeminiAPI:
    def __init__(self, api_key: str):
        self.api_key = api_key
        configure(api_key=self.api_key)
        self.model = GenerativeModel(
            "gemini-2.5-flash",
            generation_config={
                "temperature": 0.0,
                "top_p": 0.9,
                "top_k": 4,
                "max_output_tokens": 4096,
                "response_mime_type": "application/json",
            },
        )


    def load_prompt(self, filename: str) -> str:
        with open(filename, "r", encoding="utf-8") as f:
            return f.read()

    def _call_gemini(self, prompt: str):
        """Hace la llamada a Gemini y devuelve JSON crudo"""
        try:
            # Validar y limpiar el prompt
            if not isinstance(prompt, str):
                prompt = str(prompt)
            
            # Limpiar caracteres no ASCII del prompt
            prompt = prompt.encode('ascii', 'ignore').decode('ascii')
            
            response = self.model.generate_content(prompt)
            
            if not hasattr(response, 'text') or not response.text:
                return {"error": "La respuesta de la API no contiene texto"}
                
            response_text = response.text.strip()
            
            # Limpiar caracteres no ASCII de la respuesta
            response_text = response_text.encode('ascii', 'ignore').decode('ascii')
            
            # Extraer JSON de bloques de código markdown
            if '```json' in response_text:
                response_text = response_text.split('```json')[1].split('```')[0].strip()
            elif '```' in response_text:
                response_text = response_text.split('```')[1].split('```')[0].strip()
            
            # Validar y limpiar el JSON
            try:
                return clean_and_validate_json(response_text)
            except json.JSONDecodeError as e:
                print(f"Error al decodificar JSON: {e}")
                print(f"Respuesta original: {response_text[:500]}...")  # Mostrar solo los primeros 500 caracteres
                return {"error": "No se pudo procesar la respuesta de la API"}
                
        except Exception as e:
            error_msg = str(e)
            print(f"Error en _call_gemini: {error_msg}")
            
            # Información adicional para depuración
            if 'response' in locals():
                try:
                    response_text = getattr(response, 'text', 'No hay texto en la respuesta')
                    print(f"Respuesta cruda: {response_text[:500]}...")  # Mostrar solo los primeros 500 caracteres
                except Exception as debug_e:
                    print(f"Error al obtener la respuesta: {debug_e}")
                    
            return {"error": f"Error en la comunicación con la API: {error_msg}"}

    def parse_cv(self, cv_path: str) -> dict:
        """Devuelve CV como diccionario limpio"""
        cv_text = read_cv(cv_path)
        prompt = self.load_prompt("./prompts/prompt_cv.txt")
        now = datetime.now()
        actual_date = now.strftime("%B, %Y")
        # añadimos el cv al prompt
        prompt = prompt.replace("{cv_text}", cv_text)
        prompt = prompt.replace("{actual_date}", actual_date)
        raw    = self._call_gemini(prompt)
        return fill_from_template(CV_TEMPLATE, raw)

    def parse_offer(self, offer_path: str) -> dict:
        """Devuelve oferta como diccionario limpio"""
        try:
            with open(offer_path, 'r', encoding='utf-8') as f:
                offer_text = f.read().strip()
                
            # Clean the offer text - remove any trailing periods that might be in the file
            offer_text = offer_text.rstrip('.').strip()
            
            prompt = self.load_prompt("./prompts/prompt_offer.txt")
            prompt = prompt.replace("{offer_text}", offer_text)
            
            raw = self._call_gemini(prompt)
            
            # Clean the response - remove any trailing characters that might break JSON parsing
            if isinstance(raw, str):
                raw = raw.strip()
                # Remove any trailing punctuation that might have been included
                raw = raw.rstrip('.').strip()
                
            result = fill_from_template(OFFER_TEMPLATE, raw)
            
            if not result or all(v is None for v in result.values()):
                print(f"Warning: Empty or invalid response for offer: {offer_path}")
                
            return result
            
        except Exception as e:
            print(f"Error parsing offer from {offer_path}: {str(e)}")
            print(f"Raw response was: {raw if 'raw' in locals() else 'N/A'}")
            raise