# utils/ia_engine.py
import json
import requests
from sentence_transformers import SentenceTransformer
import chromadb
import os
from datetime import datetime, date, timedelta
from models import db
from models.conocimiento import Normativa, ConsultaIA, RecomendacionIA
from models.equipo import Equipo
from models.orden_trabajo import OrdenTrabajo
from models.capa import CAPA
from models.calibracion import Calibracion
import logging

logger = logging.getLogger(__name__)

class IAEngine:
    def __init__(self):
        """Inicializa el motor de IA"""
        self.model = None
        self.client = None
        self.collection = None
        self.inicializado = False
        self.ollama_url = "http://localhost:11434/api/generate"
        self.modelos_disponibles = []
        self.modelo_actual = None
        self.modo_offline = False
        
    def inicializar(self):
        """Inicializa el modelo y la base de datos vectorial"""
        try:
            # 1. Verificar conexión con Ollama
            self._verificar_ollama()
            
            # 2. Cargar modelo de embeddings (para búsqueda semántica)
            print("📚 Cargando modelo de embeddings...")
            self.model = SentenceTransformer('paraphrase-multilingual-MiniLM-L12-v2')
            
            # 3. Inicializar ChromaDB
            self.client = chromadb.PersistentClient(path="./chroma_db")
            
            # 4. Crear o obtener colección
            try:
                self.collection = self.client.get_collection("normativas_gmp")
                print("✅ Colección de normativas encontrada")
            except:
                print("📝 Creando nueva colección de normativas...")
                self.collection = self.client.create_collection("normativas_gmp")
                self._cargar_normativas_iniciales()
            
            self.inicializado = True
            print(f"🎉 Motor de IA inicializado correctamente")
            if not self.modo_offline:
                print(f"   Modelo activo: {self.modelo_actual}")
            else:
                print("   Modo offline (sin LLM)")
            
        except Exception as e:
            print(f"❌ Error al inicializar IA: {e}")
            self.inicializado = False
    
    def _verificar_ollama(self):
        """Verifica conexión con Ollama y lista modelos disponibles"""
        try:
            response = requests.get("http://localhost:11434/api/tags", timeout=3)
            if response.status_code == 200:
                data = response.json()
                self.modelos_disponibles = [m['name'] for m in data.get('models', [])]
                
                if self.modelos_disponibles:
                    print(f"✅ Conexión con Ollama exitosa")
                    print(f"📦 Modelos disponibles: {', '.join(self.modelos_disponibles)}")
                    
                    # Elegir el mejor modelo disponible
                    self.modelo_actual = self._elegir_mejor_modelo()
                    print(f"🤖 Modelo seleccionado: {self.modelo_actual}")
                    self.modo_offline = False
                else:
                    print("⚠️  Ollama conectado pero no hay modelos instalados")
                    self.modo_offline = True
            else:
                print("⚠️  Ollama no responde correctamente")
                self.modo_offline = True
                
        except requests.exceptions.ConnectionError:
            print("⚠️  No se pudo conectar a Ollama. Modo offline activado.")
            print("   Para usar el asistente IA, instala Ollama desde https://ollama.ai")
            self.modo_offline = True
        except Exception as e:
            print(f"⚠️  Error conectando a Ollama: {e}")
            self.modo_offline = True
    
    def _elegir_mejor_modelo(self):
        """Elige el mejor modelo disponible según preferencia"""
        # Lista de modelos preferidos en orden de prioridad
        preferencias = [
            'llama3.2:3b',      # Rápido y bueno
            'llama3.1:latest',   # Versión anterior pero buena
            'gemma3:4b',         # Alternativa de Google
            'llama3:latest',     # Versión original
            'mistral:latest',    # Otra alternativa
            'phi:latest',        # Modelo pequeño de Microsoft
        ]
        
        for modelo in preferencias:
            if modelo in self.modelos_disponibles:
                return modelo
        
        # Si no hay preferido, tomar el primero disponible
        if self.modelos_disponibles:
            return self.modelos_disponibles[0]
        
        return None
    
    def _cargar_normativas_iniciales(self):
        """Carga las normativas iniciales desde el archivo JSON"""
        try:
            # Verificar si el directorio data existe
            if not os.path.exists('data'):
                os.makedirs('data')
            
            # Intentar cargar desde archivo JSON
            archivo_normativas = 'data/normativas_gmp.json'
            if os.path.exists(archivo_normativas):
                with open(archivo_normativas, 'r', encoding='utf-8') as f:
                    normativas = json.load(f)
                print(f"📁 Cargando {len(normativas)} normativas desde archivo")
            else:
                # Crear normativas por defecto
                print("📝 Creando normativas por defecto")
                normativas = self._crear_normativas_default()
                with open(archivo_normativas, 'w', encoding='utf-8') as f:
                    json.dump(normativas, f, ensure_ascii=False, indent=4)
            
            contador = 0
            for norm in normativas:
                # Verificar si ya existe
                existente = Normativa.query.filter_by(codigo=norm['codigo']).first()
                if existente:
                    continue
                
                # Guardar en base de datos SQL
                nueva_normativa = Normativa(
                    codigo=norm['codigo'],
                    titulo=norm['titulo'],
                    descripcion=norm.get('descripcion', ''),
                    contenido=norm.get('contenido', norm.get('descripcion', '')),
                    tipo=norm.get('tipo', 'GMP'),
                    categoria=norm.get('categoria', 'General'),
                    subcategoria=norm.get('subcategoria', ''),
                    aplica_a=norm.get('aplica_a', ''),
                    palabras_clave=norm.get('palabras_clave', ''),
                    fecha_publicacion=datetime.strptime(norm['fecha_publicacion'], '%Y-%m-%d').date() if norm.get('fecha_publicacion') else None,
                    version=norm.get('version', '1.0')
                )
                db.session.add(nueva_normativa)
                db.session.flush()
                
                # Crear embedding
                texto_para_embedding = f"{norm['codigo']} {norm['titulo']} {norm.get('descripcion', '')} {norm.get('contenido', '')} {norm.get('palabras_clave', '')}"
                embedding = self.model.encode(texto_para_embedding).tolist()
                
                # Guardar en ChromaDB
                self.collection.add(
                    embeddings=[embedding],
                    documents=[texto_para_embedding],
                    metadatas=[{
                        'id': nueva_normativa.id,
                        'codigo': norm['codigo'],
                        'titulo': norm['titulo'],
                        'tipo': norm.get('tipo', 'GMP'),
                        'categoria': norm.get('categoria', 'General')
                    }],
                    ids=[f"norm_{nueva_normativa.id}"]
                )
                contador += 1
            
            db.session.commit()
            print(f"✅ Se cargaron {contador} normativas nuevas")
            print(f"📊 Total en base de datos: {Normativa.query.count()}")
            
        except Exception as e:
            print(f"❌ Error al cargar normativas: {e}")
            db.session.rollback()
    
    def _crear_normativas_default(self):
        """Crea normativas por defecto si no existe el archivo"""
        return [
            {
                "codigo": "ANMAT-DISP-2819/99",
                "titulo": "Buenas Prácticas de Manufactura",
                "descripcion": "Reglamentación de Buenas Prácticas de Manufactura",
                "contenido": "Establece los requisitos mínimos de Buenas Prácticas de Manufactura que deben cumplir los establecimientos elaboradores de productos farmacéuticos.",
                "tipo": "ANMAT",
                "categoria": "BPM",
                "subcategoria": "General",
                "aplica_a": "Todos los establecimientos farmacéuticos",
                "palabras_clave": "BPM, GMP, buenas prácticas, manufactura, calidad",
                "fecha_publicacion": "1999-12-15",
                "version": "1.0"
            },
            {
                "codigo": "GMP-CAL-2023/03",
                "titulo": "Guidelines on Calibration of Equipment",
                "descripcion": "Calibración de equipos",
                "contenido": "Provides requirements for calibration of equipment used in pharmaceutical manufacturing.",
                "tipo": "GMP",
                "categoria": "Calibración",
                "subcategoria": "Equipos",
                "aplica_a": "Equipos de fabricación y control",
                "palabras_clave": "calibration, equipment, standards, traceability",
                "fecha_publicacion": "2023-03-20",
                "version": "1.0"
            }
        ]
    
    def consultar(self, pregunta, usuario=None, top_k=3):
        """Realiza una consulta al motor de IA"""
        if not self.inicializado:
            return self._consultar_simulado(pregunta, usuario)
        
        try:
            # 1. BUSCAR NORMATIVAS RELEVANTES (RAG)
            embedding_pregunta = self.model.encode(pregunta).tolist()
            
            resultados = self.collection.query(
                query_embeddings=[embedding_pregunta],
                n_results=top_k
            )
            
            normativas_encontradas = []
            if resultados and resultados.get('metadatas') and resultados['metadatas'][0]:
                for metadata in resultados['metadatas'][0]:
                    normativa = Normativa.query.get(metadata['id'])
                    if normativa:
                        normativa.veces_consultada += 1
                        normativa.ultima_consulta = datetime.utcnow()
                        
                        normativas_encontradas.append({
                            'id': normativa.id,
                            'codigo': normativa.codigo,
                            'titulo': normativa.titulo,
                            'descripcion': normativa.descripcion,
                            'contenido': normativa.contenido[:500] + "..." if len(normativa.contenido) > 500 else normativa.contenido,
                            'tipo': normativa.tipo,
                            'categoria': normativa.categoria
                        })
            
            # 2. GENERAR RESPUESTA CON OLLAMA (si está disponible)
            if not self.modo_offline and self.modelo_actual:
                respuesta = self._consultar_ollama(pregunta, normativas_encontradas)
            else:
                respuesta = self._generar_respuesta_fallback(pregunta, normativas_encontradas)
            
            # 3. GUARDAR CONSULTA
            consulta = ConsultaIA(
                usuario=usuario,
                pregunta=pregunta,
                respuesta=respuesta,
                normativas_referenciadas=','.join([str(n['id']) for n in normativas_encontradas])
            )
            db.session.add(consulta)
            db.session.commit()
            
            return {
                'respuesta': respuesta,
                'normativas': normativas_encontradas,
                'modelo_usado': self.modelo_actual if not self.modo_offline else 'offline'
            }
            
        except Exception as e:
            print(f"❌ Error en consulta: {e}")
            return self._consultar_simulado(pregunta, usuario)
    
    def _consultar_ollama(self, pregunta, normativas):
        """Consulta a Ollama con el contexto de las normativas"""
        try:
            # Construir el contexto con las normativas encontradas
            contexto = "NORMATIVAS GMP/ANMAT DISPONIBLES:\n\n"
            if normativas:
                for n in normativas[:3]:
                    contexto += f"--- {n['codigo']}: {n['titulo']} ---\n"
                    contexto += f"{n['contenido']}\n\n"
            else:
                contexto += "No se encontraron normativas específicas en la base de datos.\n"
                contexto += "Responde basándote en tu conocimiento general sobre GMP.\n\n"
            
            # Crear el prompt
            prompt = f"""{contexto}

Basado en la información anterior, responde a la siguiente pregunta como un experto en normativas GMP y ANMAT para la industria farmacéutica:

PREGUNTA: {pregunta}

INSTRUCCIONES IMPORTANTES:
- Si hay normativas disponibles, ÚSALAS como fuente principal y cítalas (ej: "Según ANMAT DISP 2819/99...")
- Si no hay normativas específicas, responde con tu conocimiento general pero indícalo
- Sé preciso, técnico y profesional
- Si la pregunta no está relacionada con GMP/farmacéutica, indícalo amablemente
- Responde en español, en el mismo idioma de la pregunta

RESPUESTA:"""
            
            # Llamar a Ollama con el modelo actual
            payload = {
                "model": self.modelo_actual,
                "prompt": prompt,
                "stream": False,
                "temperature": 0.3,
                "max_tokens": 1000
            }
            
            response = requests.post(self.ollama_url, json=payload, timeout=30)
            
            if response.status_code == 200:
                return response.json()['response']
            else:
                print(f"Error Ollama ({response.status_code}): {response.text}")
                return self._generar_respuesta_fallback(pregunta, normativas)
                
        except requests.exceptions.Timeout:
            print("⏰ Timeout en consulta a Ollama (muy lento)")
            return self._generar_respuesta_fallback(pregunta, normativas)
        except Exception as e:
            print(f"❌ Error en consulta Ollama: {e}")
            return self._generar_respuesta_fallback(pregunta, normativas)
    
    def _generar_respuesta_fallback(self, pregunta, normativas):
        """Respuesta de respaldo cuando Ollama no funciona"""
        if normativas:
            respuesta = f"📚 **Basado en las normativas encontradas:**\n\n"
            for n in normativas[:2]:
                respuesta += f"**{n['codigo']}**: {n['descripcion']}\n\n"
            return respuesta
        else:
            return "No encontré normativas específicas para tu consulta. Por favor intenta con otra pregunta o instala Ollama para respuestas más completas."
    
    def _consultar_simulado(self, pregunta, usuario=None):
        """Modo simulado cuando Chroma no está disponible"""
        normativas = Normativa.query.limit(3).all()
        
        normativas_encontradas = []
        for norm in normativas:
            normativas_encontradas.append({
                'id': norm.id,
                'codigo': norm.codigo,
                'titulo': norm.titulo,
                'descripcion': norm.descripcion,
                'contenido': norm.contenido[:200] + "...",
                'tipo': norm.tipo,
                'categoria': norm.categoria
            })
        
        respuesta = self._generar_respuesta_fallback(pregunta, normativas_encontradas)
        
        try:
            consulta = ConsultaIA(
                usuario=usuario,
                pregunta=pregunta,
                respuesta=respuesta,
                normativas_referenciadas=','.join([str(n['id']) for n in normativas_encontradas])
            )
            db.session.add(consulta)
            db.session.commit()
        except:
            pass
        
        return {
            'respuesta': respuesta,
            'normativas': normativas_encontradas
        }
    
    def generar_recomendaciones(self, usuario=None):
        """Genera recomendaciones basadas en el estado del sistema"""
        recomendaciones = []
        try:
            hoy = date.today()
            
            # Calibraciones próximas a vencer
            proximas_calibraciones = Calibracion.query.filter(
                Calibracion.fecha_proxima <= hoy + timedelta(days=30),
                Calibracion.fecha_proxima >= hoy,
                Calibracion.estado == 'Activo'
            ).all()
            
            for cal in proximas_calibraciones[:3]:
                dias = (cal.fecha_proxima - hoy).days
                rec = RecomendacionIA(
                    tipo='calibracion',
                    equipo_id=cal.equipo_id,
                    titulo=f"Calibración próxima a vencer",
                    descripcion=f"El instrumento {cal.instrumento} vence en {dias} días",
                    prioridad='Alta' if dias <= 7 else 'Media'
                )
                recomendaciones.append(rec)
            
            for rec in recomendaciones:
                db.session.add(rec)
            db.session.commit()
            
        except Exception as e:
            print(f"Error generando recomendaciones: {e}")
        
        return recomendaciones
    
    def obtener_recomendaciones(self, solo_no_leidas=True):
        """Obtiene las recomendaciones generadas"""
        query = RecomendacionIA.query.order_by(RecomendacionIA.created_at.desc())
        if solo_no_leidas:
            query = query.filter_by(leida=False)
        return query.limit(10).all()
    
    def marcar_recomendacion_leida(self, rec_id):
        """Marca una recomendación como leída"""
        rec = RecomendacionIA.query.get(rec_id)
        if rec:
            rec.leida = True
            db.session.commit()
            return True
        return False

# Instancia global del motor
ia_engine = IAEngine()