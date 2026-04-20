# utils/scraper_anmat_completo.py
import requests
from bs4 import BeautifulSoup
import logging
from datetime import datetime
import time
import re

logger = logging.getLogger(__name__)

class ScraperANMATCompleto:
    def __init__(self):
        self.fuentes = [
            {
                'nombre': 'ANMAT Medicamentos',
                'url': 'http://www.anmat.gob.ar/webanmat/normativas_medicamentos_cuerpo.asp',
                'tipo': 'tabla'
            },
            {
                'nombre': 'ANMAT Productos Médicos',
                'url': 'https://www.anmat.gob.ar/webanmat/normativas_productosmedicos_cuerpo.asp',
                'tipo': 'tabla'
            },
            {
                'nombre': 'ANMAT Alimentos',
                'url': 'http://www.anmat.gob.ar/webanmat/normativas_alimentos_cuerpo.asp',
                'tipo': 'tabla'
            },
            {
                'nombre': 'ANMAT Cosméticos',
                'url': 'http://www.anmat.gob.ar/webanmat/normativas_cosmeticos_cuerpo.asp',
                'tipo': 'tabla'
            },
            {
                'nombre': 'ANMAT Domisanitarios',
                'url': 'http://www.anmat.gob.ar/webanmat/normativas_domisanitarios_cuerpo.asp',
                'tipo': 'tabla'
            },
            {
                'nombre': 'Boletín Oficial',
                'url': 'https://www.boletinoficial.gob.ar/buscador?text=ANMAT&seccion=1',
                'tipo': 'boletin'
            }
        ]
    
    def scrapear_todo(self):
        """Scrapea todas las normativas de todas las fuentes"""
        todas_las_normativas = []
        
        for fuente in self.fuentes:
            try:
                logger.info(f"📡 Scrapeando: {fuente['nombre']}")
                
                if fuente['tipo'] == 'tabla':
                    normativas = self._scrapear_tabla_anmat(fuente)
                elif fuente['tipo'] == 'boletin':
                    normativas = self._scrapear_boletin_oficial(fuente)
                
                todas_las_normativas.extend(normativas)
                logger.info(f"✅ {len(normativas)} normativas encontradas en {fuente['nombre']}")
                
                # Pausa para no saturar el servidor
                time.sleep(2)
                
            except Exception as e:
                logger.error(f"Error scrapeando {fuente['nombre']}: {e}")
        
        return todas_las_normativas
    
    def _scrapear_tabla_anmat(self, fuente):
        """Scrapea las tablas de normativas del sitio de ANMAT"""
        try:
            headers = {'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'}
            response = requests.get(fuente['url'], headers=headers, timeout=15)
            response.encoding = 'latin-1'  # Importante: ANMAT usa latin-1
            
            soup = BeautifulSoup(response.text, 'html.parser')
            normativas = []
            
            # Buscar todas las filas de la tabla
            filas = soup.select('tr')
            
            for fila in filas:
                celdas = fila.find_all('td')
                if len(celdas) >= 3:
                    # Formato típico: Año | Tipo | Descripción
                    año = celdas[0].get_text(strip=True)
                    tipo = celdas[1].get_text(strip=True)
                    descripcion = celdas[2].get_text(strip=True)
                    
                    # Extraer número de disposición/resolución
                    numero_match = re.search(r'(Disposición|Resolución|Ley|Decreto)\s*(N[°]?\s*[\d/-]+)', descripcion, re.IGNORECASE)
                    numero = numero_match.group(0) if numero_match else ''
                    
                    # Extraer título (primera línea)
                    titulo = descripcion.split('\n')[0] if '\n' in descripcion else descripcion[:100]
                    
                    # Buscar link si existe
                    link = celdas[2].find('a')
                    url = link.get('href') if link else ''
                    if url and not url.startswith('http'):
                        url = 'https://www.anmat.gob.ar' + url
                    
                    normativas.append({
                        'codigo': numero,
                        'titulo': titulo,
                        'descripcion': descripcion,
                        'contenido': descripcion,
                        'tipo': 'ANMAT',
                        'categoria': fuente['nombre'].replace('ANMAT ', ''),
                        'año': año,
                        'fecha_publicacion': f"{año}-01-01" if año.isdigit() else None,
                        'url_fuente': url or fuente['url'],
                        'tipo_norma': tipo
                    })
            
            return normativas
            
        except Exception as e:
            logger.error(f"Error scraping tabla: {e}")
            return []
    
    def _scrapear_boletin_oficial(self, fuente):
        """Scrapea el Boletín Oficial buscando normativas ANMAT"""
        try:
            headers = {'User-Agent': 'Mozilla/5.0'}
            response = requests.get(fuente['url'], headers=headers, timeout=15)
            soup = BeautifulSoup(response.text, 'html.parser')
            
            normativas = []
            
            # Buscar resultados
            resultados = soup.select('.resultado')
            
            for res in resultados[:20]:  # Últimos 20 resultados
                titulo_elem = res.select_one('h3 a')
                fecha_elem = res.select_one('.fecha')
                extracto = res.select_one('.extracto')
                
                if titulo_elem:
                    titulo = titulo_elem.get_text(strip=True)
                    url = titulo_elem.get('href')
                    if not url.startswith('http'):
                        url = 'https://www.boletinoficial.gob.ar' + url
                    
                    fecha = fecha_elem.get_text(strip=True) if fecha_elem else ''
                    
                    normativas.append({
                        'codigo': self._extraer_numero_normativa(titulo),
                        'titulo': titulo,
                        'descripcion': extracto.get_text(strip=True) if extracto else '',
                        'contenido': '',
                        'tipo': 'ANMAT',
                        'categoria': 'Boletín Oficial',
                        'fecha_publicacion': self._convertir_fecha(fecha),
                        'url_fuente': url
                    })
            
            return normativas
            
        except Exception as e:
            logger.error(f"Error scraping boletín: {e}")
            return []
    
    def _extraer_numero_normativa(self, texto):
        """Extrae el número de normativa del texto"""
        patrones = [
            r'(Disposición|Resolución|Ley|Decreto)\s*(N[°]?\s*[\d/-]+)',
            r'(DI-\d{4}-\d+-APN-ANMAT)',
            r'(\d+/\d{4})'
        ]
        
        for patron in patrones:
            match = re.search(patron, texto, re.IGNORECASE)
            if match:
                return match.group(0)
        
        return ''
    
    def _convertir_fecha(self, texto_fecha):
        """Convierte texto de fecha a formato ISO"""
        try:
            # Intentar varios formatos
            formatos = ['%d/%m/%Y', '%Y-%m-%d', '%d de %B de %Y']
            for formato in formatos:
                try:
                    fecha = datetime.strptime(texto_fecha.strip(), formato)
                    return fecha.strftime('%Y-%m-%d')
                except:
                    continue
            return None
        except:
            return None