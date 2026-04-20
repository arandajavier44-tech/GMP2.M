# routes/__init__.py
from flask import Blueprint

# Importar blueprints para que estén disponibles
from routes.auth import auth_bp
from routes.equipos import equipos_bp
from routes.dashboard import dashboard_bp

# Estos archivos ya existen, solo importamos
from routes.ordenes import ordenes_bp
from routes.calibraciones import calibraciones_bp