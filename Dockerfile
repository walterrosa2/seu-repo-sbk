FROM python:3.11-slim

WORKDIR /app

# ------------------------------------
# Dependências de sistema básicas
# ------------------------------------
RUN apt-get update && apt-get install -y \
    fontconfig \
    libjpeg62-turbo \
    xfonts-base \
    xfonts-75dpi \
    wget \
    ca-certificates \
    && rm -rf /var/lib/apt/lists/*

# ------------------------------------
# Instalar wkhtmltopdf para Debian 12 (bookworm)
# Versão 0.12.6.1-3 específica para bookworm
# ------------------------------------
RUN wget -O wkhtmltox.deb \
    https://github.com/wkhtmltopdf/packaging/releases/download/0.12.6.1-3/wkhtmltox_0.12.6.1-3.bookworm_amd64.deb \
    && apt-get update \
    && apt-get install -y ./wkhtmltox.deb \
    && rm wkhtmltox.deb \
    && rm -rf /var/lib/apt/lists/*

# (Opcional) Conferir se o binário está disponível:
# RUN wkhtmltopdf --version

# ------------------------------------
# Dependências Python
# ------------------------------------
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copia o restante da aplicação
COPY . .

# ------------------------------------
# Config do Streamlit
# ------------------------------------
ENV STREAMLIT_SERVER_HEADLESS=true
ENV STREAMLIT_BROWSER_GATHER_USAGE_STATS=false

# ------------------------------------
# Comando final
# - LOCAL: sem PORT definido -> usa 8501
# - RAILWAY: PORT é injetado e o sh expande a variável
# ------------------------------------


# ------------------------------------
# Comando final — Railway usa $PORT
# ------------------------------------
CMD ["sh", "-c", "streamlit run interface_frontend.py --server.address=0.0.0.0 --server.port=${PORT:-8501}"]



