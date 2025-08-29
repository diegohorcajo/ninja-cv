import traceback
import sys
from fastapi import FastAPI, UploadFile, Form, Request, Response, HTTPException
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from fastapi.responses import HTMLResponse, FileResponse, RedirectResponse, JSONResponse
from fastapi.middleware.cors import CORSMiddleware
import os
import uvicorn
from pathlib import Path
import json
from cv_matcher import matcher  # tu instancia global de CVMatcher

# uvicorn main:app --reload

app = FastAPI()

# Manejador de excepciones global
@app.exception_handler(Exception)
async def global_exception_handler(request: Request, exc: Exception):
    exc_type, exc_value, exc_traceback = sys.exc_info()
    error_details = {
        "error": str(exc),
        "type": exc_type.__name__,
        "file": exc_traceback.tb_frame.f_code.co_filename,
        "line": exc_traceback.tb_lineno,
        "traceback": traceback.format_exc()
    }
    print("\n" + "="*50)
    print("ERROR DETALLADO:")
    print(json.dumps(error_details, indent=2))
    print("="*50 + "\n")
    
    # Para depuración, devolvemos el error completo
    return JSONResponse(
        status_code=500,
        content={"error": "Error interno del servidor", "details": error_details}
    )

# Configurar CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # En producción, reemplaza con el origen de tu frontend
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Configurar directorios
BASE_DIR = Path(__file__).parent
TMP_DIR  = Path("/tmp")
STATIC_DIR = BASE_DIR / "static"
TEMPLATES_DIR = BASE_DIR / "templates"

# Crear directorios si no existen
TMP_DIR.mkdir(exist_ok=True)
STATIC_DIR.mkdir(exist_ok=True)
TEMPLATES_DIR.mkdir(exist_ok=True)

# Montar archivos estáticos
app.mount("/static", StaticFiles(directory=str(STATIC_DIR)), name="static")
templates = Jinja2Templates(directory=str(TEMPLATES_DIR))

# Servir archivo HTML principal
@app.get("/", response_class=HTMLResponse)
async def read_root(request: Request):
    return FileResponse(str(STATIC_DIR / "index.html"))

# Servir archivos estáticos
@app.get("/{filename}")
async def get_static(filename: str):
    if filename == "favicon.ico":
        return FileResponse(str(STATIC_DIR / "favicon.ico"))
    return FileResponse(str(STATIC_DIR / filename))

# Redirigir favicon.ico a la ruta estática
@app.get("/favicon.ico")
async def favicon():
    return FileResponse(str(STATIC_DIR / "favicon.ico"))

@app.post("/match_cv/")
async def match_cv(offer_text: str = Form(...), 
                   cv_file: UploadFile = None):
    # Constantes de validación
    MIN_OFFER_LENGTH = 100
    MAX_OFFER_LENGTH = 10000
    MIN_CV_LENGTH = 10
    
    # Validar longitud del texto de la oferta
    offer_length = len(offer_text)
    if offer_length < MIN_OFFER_LENGTH:
        return {"error": f"The text of the offer is too short. Minimum required: {MIN_OFFER_LENGTH} characters"}
    if offer_length > MAX_OFFER_LENGTH:
        return {"error": f"The text of the offer is too long. Maximum allowed: {MAX_OFFER_LENGTH} characters"}
    
    if cv_file is None:
        return {"error": "No CV file was uploaded"}
        
    # Leer el contenido del archivo una sola vez
    content = await cv_file.read()
    
    # Validar tamaño mínimo del CV
    if len(content) < MIN_CV_LENGTH:
        return {"error": f"The CV file is too small. Minimum required: {MIN_CV_LENGTH} characters"}

    # Validar tamaño máximo del archivo (5MB)
    MAX_FILE_SIZE = 5 * 1024 * 1024  # 5MB en bytes
    if len(content) > MAX_FILE_SIZE:
        return {"error": "The file is too large. Maximum allowed: 5MB"}
    
    # Guardar el contenido para su posterior uso
    file_content = content
    await cv_file.seek(0)
    
    # Guardar CV temporalmente cambiando el nombre a cv.pdf
    cv_file.filename = "cv.pdf"
    cv_path = os.path.join(TMP_DIR, cv_file.filename)
    with open(cv_path, "wb") as f:
        f.write(content)

    # Guardar oferta como txt temporal
    offer_path = os.path.join(TMP_DIR, "offer.txt")
    with open(offer_path, "w", encoding="utf-8") as f:
        f.write(offer_text)

    # Calcular similitud usando tu matcher
    try:
        scores = matcher.final_score(offer_path, cv_path)
    except Exception as e:
        return {"error": str(e)}

    return scores


if __name__ == "__main__":
    import os, uvicorn
    port = int(os.environ.get("PORT", 8000))
    # reload
    uvicorn.reload = True
    uvicorn.run("main:app", host="0.0.0.0", port=port)