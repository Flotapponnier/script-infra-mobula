FROM python:3.11-slim

WORKDIR /app

# Installer les dépendances
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copier le script
COPY alert_summary.py .

# Rendre le script exécutable
RUN chmod +x alert_summary.py

# Exécuter le script
CMD ["python3", "alert_summary.py"]
