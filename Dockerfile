# 1. Empezamos con la misma imagen de Python
FROM python:3.12-slim

# 2. Establecemos nuestro directorio de trabajo en /app
WORKDIR /app

# --- CAMBIO IMPORTANTE ---
# 3. Copiamos el fichero requirements.txt DESDE DENTRO de tu carpeta 'project'
#    El '.' significa "cópialo aquí", en nuestro directorio de trabajo (/app).
COPY project/requirements.txt .

# 4. Instalamos las dependencias. Ahora pip encontrará requirements.txt en /app.
RUN pip install --no-cache-dir --upgrade -r requirements.txt

# --- CAMBIO IMPORTANTE ---
# 5. Copiamos TODO EL CONTENIDO de tu carpeta 'project' al directorio de trabajo /app.
#    Esto significa que main.py, static/, prompts/, etc., estarán directamente dentro de /app.
COPY project/ .

# --- CAMBIO IMPORTANTE ---
# 6. Como ahora main.py está en la raíz de /app, el comando para iniciar es más simple.
#    Ya no necesitamos "project.main:app", sino simplemente "main:app".
CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "7860"]