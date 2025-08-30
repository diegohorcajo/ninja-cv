# Versión Definitiva y Corregida

# 1. Empezamos con la imagen de Python
FROM python:3.12-slim

# 2. CREAMOS Y NOS MOVEMOS a /app PRIMERO. Es la mejor práctica.
WORKDIR /app

# 3. Copiamos SÓLO el fichero de requisitos (que está dentro de project).
COPY project/requirements.txt .

# 4. Instalamos las dependencias.
RUN pip install --no-cache-dir --upgrade -r requirements.txt

# 5. Copiamos TODO EL CONTENIDO de 'project' (incluyendo la carpeta templates).
#    Esta ÚNICA línea es suficiente porque todo tu código está dentro de 'project'.
COPY project/ .

# 6. El comando para iniciar la aplicación.
CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "7860"]