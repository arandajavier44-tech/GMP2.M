# run.py
from app import create_app, start_scheduler
import os
from dotenv import load_dotenv

# Cargar variables de entorno desde .env
load_dotenv()

app = create_app()

# Iniciar scheduler SOLO una vez (evita duplicados en modo debug)
if os.environ.get('WERKZEUG_RUN_MAIN') == 'true':
    start_scheduler(app)
    print("🚀 Scheduler iniciado en el proceso principal")

if __name__ == '__main__':
    app.run(debug=True, host='0.0.0.0', port=5000)