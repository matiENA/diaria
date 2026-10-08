# ==============================================================================
# Dockerfile Multi-Runtime (Python 3.11 + Node.js 20) para Render Cloud
# ==============================================================================
FROM python:3.11-slim-bullseye

# Instalar Node.js 20 y utilidades del sistema
RUN apt-get update && apt-get install -y --no-install-recommends \
    curl \
    ca-certificates \
    gnupg \
    && mkdir -p /etc/apt/keyrings \
    && curl -fsSL https://deb.nodesource.com/gpgkey/nodesource-repo.gpg.key | gpg --dearmor -o /etc/apt/keyrings/nodesource.gpg \
    && echo "deb [signed-by=/etc/apt/keyrings/nodesource.gpg] https://deb.nodesource.com/node_20.x nodistro main" | tee /etc/apt/sources.list.d/nodesource.list \
    && apt-get update \
    && apt-get install -y nodejs \
    && apt-get clean \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# Instalar dependencias de Node
COPY package*.json ./
RUN npm install --production

# Instalar dependencias de Python
COPY requirements.txt ./
RUN pip install --no-cache-dir -r requirements.txt

# Copiar el código fuente
COPY . .

# Variables de entorno por defecto
ENV PORT=10000
ENV ENABLE_SCHEDULER=true
ENV PYTHONUNBUFFERED=1

EXPOSE 10000

# Comando de inicio del servidor con Uvicorn
CMD ["sh", "-c", "uvicorn server_render:app --host 0.0.0.0 --port ${PORT}"]
