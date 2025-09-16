import requests
from bs4 import BeautifulSoup
import time
import re
import os
import signal
import sys
from urllib.parse import urljoin
from collections import deque
import json
import logging
from concurrent.futures import ThreadPoolExecutor, as_completed
import threading
from queue import Queue, Empty
import random

class ParallelWikipediaCrawler:
    def __init__(self, num_workers=5):
        self.base_url = "https://pt.wikipedia.org/"
        
        # LISTAS FOCADAS: Páginas que garantidamente têm muitas biografias
        self.biography_sources = [
            # Categorias por ano de nascimento (muito produtivas)
            "wiki/Categoria:Nascidos_em_1990", "wiki/Categoria:Nascidos_em_1985",
            "wiki/Categoria:Nascidos_em_1980", "wiki/Categoria:Nascidos_em_1975",
            "wiki/Categoria:Nascidos_em_1970", "wiki/Categoria:Nascidos_em_1965",
            
            # Profissões específicas
            "wiki/Categoria:Atores_do_Brasil", "wiki/Categoria:Cantores_do_Brasil",
            "wiki/Categoria:Políticos_do_Brasil", "wiki/Categoria:Escritores_do_Brasil",
            "wiki/Categoria:Jogadores_de_futebol_do_Brasil",
            
            # Listas diretas de pessoas
            "wiki/Lista_de_presidentes_do_Brasil",
            "wiki/Lista_de_governadores_de_São_Paulo",
            "wiki/Lista_de_prefeitos_de_São_Paulo",
            
            # Categorias internacionais produtivas
            "wiki/Categoria:Atores_dos_Estados_Unidos",
            "wiki/Categoria:Cantores_dos_Estados_Unidos",
        ]
        
        self.num_workers = num_workers
        self.visited_links = set()
        self.person_pages = set()
        self.collected_count = 0
        self.target_count = 1000
        
        # Filas thread-safe
        self.url_queue = Queue()
        self.results_queue = Queue()
        
        # Controles thread-safe
        self.lock = threading.Lock()
        self.running = True
        
        # Inicializar filas
        for source in self.biography_sources:
            self.url_queue.put(source)
        
        # Configurar logging
        logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
        self.logger = logging.getLogger(__name__)
        
        # Diretório de saída
        self.output_dir = "wikipedia_pessoas"
        if not os.path.exists(self.output_dir):
            os.makedirs(self.output_dir)
        
        # Controle de interrupção
        signal.signal(signal.SIGINT, self.signal_handler)

    def signal_handler(self, signum, frame):
        """Para todas as threads e salva dados"""
        print(f"\n{'='*50}")
        print("INTERRUPÇÃO - PARANDO THREADS...")
        self.running = False
        self.save_statistics()
        print(f"Pessoas coletadas: {self.collected_count}")
        sys.exit(0)

    def create_session(self):
        """Cria sessão HTTP otimizada"""
        session = requests.Session()
        session.headers.update({
            'User-Agent': f'Mozilla/5.0 (Windows NT 10.0; Win64; x64) Chrome/{random.randint(90,120)}.0.0.0'
        })
        return session

    def is_person_ultra_fast(self, soup):
        """Detecção ultra-rápida focada apenas no essencial"""
        try:
            # Título
            title_elem = soup.find("span", {"class": "mw-page-title-main"})
            if not title_elem:
                return False, ""
            
            title = title_elem.get_text(strip=True)
            title_lower = title.lower()
            
            # Exclusões imediatas por título
            if any(x in title_lower for x in ['lista de', 'categoria:', 'guerra', 'batalha', 'cidade']):
                return False, title
            
            # Busca rápida por datas no título (indica biografia)
            if re.search(r'\(\d{4}[-–]\d{4}\)', title) or re.search(r'\(\d{4}[-–]\)', title):
                return True, title
            
            # Infobox check mínimo
            infobox = soup.find("table", {"class": "infobox"})
            if not infobox:
                return False, title
            
            # Busca APENAS por campos críticos
            infobox_text = infobox.get_text().lower()[:500]  # Apenas primeiros 500 chars
            
            person_indicators = ['nascimento:', 'morte:', 'cônjuge:', 'ocupação:', 'profissão:']
            person_count = sum(1 for indicator in person_indicators if indicator in infobox_text)
            
            if person_count >= 2:
                return True, title
            elif person_count == 1:
                # Check ultra-rápido do primeiro parágrafo
                content = soup.find("div", {"id": "mw-content-text"})
                if content:
                    first_para = content.find("p")
                    if first_para:
                        para_text = first_para.get_text()[:150].lower()
                        bio_patterns = [r'\bé um \w+', r'\bé uma \w+', r'\bfoi um \w+', r'\bfoi uma \w+']
                        if any(re.search(pattern, para_text) for pattern in bio_patterns):
                            return True, title
            
            return False, title
            
        except Exception:
            return False, ""

    def extract_category_links(self, soup):
        """Extrai links de páginas de categoria de forma otimizada"""
        links = []
        try:
            # Para categorias, buscar na área específica de membros
            category_members = soup.find("div", {"id": "mw-pages"})
            if category_members:
                category_links = category_members.find_all("a", href=re.compile(r"^/wiki/[^:]+$"))
                for link in category_links:
                    href = link.get('href')
                    if href and self.should_visit_url(href):
                        links.append(href)
            
            # Se não encontrou área de categoria, buscar links normais
            if not links:
                content = soup.find("div", {"id": "mw-content-text"})
                if content:
                    all_links = content.find_all("a", href=re.compile(r"^/wiki/[^:]+$"))
                    for link in all_links[:30]:  # Máximo 30
                        href = link.get('href')
                        if href and self.should_visit_url(href):
                            links.append(href)
            
        except Exception as e:
            self.logger.error(f"Erro ao extrair links de categoria: {e}")
        
        return links

    def should_visit_url(self, href):
        """Filtro rápido de URLs"""
        if not href or not href.startswith('/wiki/'):
            return False
        
        # Exclusões rápidas
        exclusions = [':', 'Lista_de_', 'Categoria:', 'Anexo:', 'Portal:']
        if any(exc in href for exc in exclusions):
            return False
        
        # Padrões que sugerem nomes de pessoas
        if re.search(r'/wiki/[A-Z][a-z]+_[A-Z][a-z]+', href):  # Nome_Sobrenome
            return True
        
        # Aceitar se não há exclusões óbvias
        return True

    def worker_thread(self, worker_id):
        """Thread worker que processa URLs"""
        session = self.create_session()
        self.logger.info(f"Worker {worker_id} iniciado")
        
        while self.running and self.collected_count < self.target_count:
            try:
                # Pegar URL da fila com timeout
                try:
                    current_url = self.url_queue.get(timeout=2)
                except Empty:
                    continue
                
                full_url = urljoin(self.base_url, current_url)
                
                # Verificar se já foi visitado
                with self.lock:
                    if full_url in self.visited_links:
                        self.url_queue.task_done()
                        continue
                    self.visited_links.add(full_url)
                
                try:
                    response = session.get(full_url, timeout=8)
                    response.raise_for_status()
                    
                    soup = BeautifulSoup(response.content, 'html.parser')
                    
                    # Verificar se é pessoa
                    is_person, title = self.is_person_ultra_fast(soup)
                    
                    if is_person:
                        # Salvar página
                        if self.save_page_safe(response.text, title):
                            with self.lock:
                                self.collected_count += 1
                                self.person_pages.add(full_url)
                            
                            self.logger.info(f"✅ Worker{worker_id} - PESSOA ({self.collected_count}/{self.target_count}): {title}")
                    
                    # Extrair novos links se ainda precisamos
                    if self.collected_count < self.target_count:
                        if 'Categoria:' in current_url:
                            new_links = self.extract_category_links(soup)
                        else:
                            new_links = self.extract_bio_links(soup)
                        
                        # Adicionar links à fila
                        for link in new_links[:10]:  # Máximo 10 por página
                            self.url_queue.put(link)
                    
                    # Pausa mínima
                    time.sleep(0.3)
                    
                except requests.RequestException as e:
                    self.logger.error(f"Worker {worker_id} - Erro HTTP em {current_url}: {e}")
                
                self.url_queue.task_done()
                
            except Exception as e:
                self.logger.error(f"Worker {worker_id} - Erro geral: {e}")
                break
        
        self.logger.info(f"Worker {worker_id} finalizado")

    def extract_bio_links(self, soup):
        """Extrai links com foco em biografias"""
        links = []
        try:
            content = soup.find("div", {"id": "mw-content-text"})
            if not content:
                return links
            
            # Procurar em parágrafos que mencionam pessoas
            paragraphs = content.find_all("p")[:5]
            for para in paragraphs:
                para_text = para.get_text().lower()
                
                # Se menciona biografias, extrair links
                if any(word in para_text for word in ['nasceu', 'político', 'ator', 'escritor', 'cantor']):
                    para_links = para.find_all("a", href=re.compile(r"^/wiki/[^:]+$"))
                    for link in para_links:
                        href = link.get('href')
                        if self.should_visit_url(href):
                            links.append(href)
            
        except Exception:
            pass
        
        return links

    def save_page_safe(self, content, title):
        """Salva página de forma thread-safe"""
        try:
            safe_title = re.sub(r'[<>:"/\\|?*]', '_', title)[:100]
            filename = f"{safe_title}.html"
            filepath = os.path.join(self.output_dir, filename)
            
            # Lock para evitar conflitos de escrita
            with self.lock:
                if os.path.exists(filepath):
                    return False
                
                with open(filepath, 'w', encoding='utf-8') as f:
                    f.write(content)
            
            return True
        except Exception as e:
            self.logger.error(f"Erro ao salvar {title}: {e}")
            return False

    def monitor_progress(self):
        """Thread de monitoramento do progresso"""
        start_time = time.time()
        last_count = 0
        
        while self.running and self.collected_count < self.target_count:
            time.sleep(10)  # Check a cada 10 segundos
            
            current_count = self.collected_count
            elapsed = time.time() - start_time
            rate = current_count / elapsed if elapsed > 0 else 0
            
            if current_count != last_count:
                eta = (self.target_count - current_count) / rate if rate > 0 else float('inf')
                self.logger.info(f"PROGRESSO: {current_count}/{self.target_count} pessoas "
                               f"({rate:.2f} pessoas/min) - ETA: {eta/60:.1f}min")
                last_count = current_count

    def run_parallel_crawler(self):
        """Executa crawler paralelo"""
        self.logger.info(f"Iniciando crawler PARALELO com {self.num_workers} workers")
        self.logger.info(f"Meta: {self.target_count} pessoas")
        
        # Iniciar thread de monitoramento
        monitor_thread = threading.Thread(target=self.monitor_progress, daemon=True)
        monitor_thread.start()
        
        # Iniciar workers
        with ThreadPoolExecutor(max_workers=self.num_workers) as executor:
            # Submeter workers
            futures = []
            for i in range(self.num_workers):
                future = executor.submit(self.worker_thread, i)
                futures.append(future)
            
            # Aguardar conclusão ou meta atingida
            try:
                while self.running and self.collected_count < self.target_count:
                    time.sleep(1)
                    
                    # Verificar se todos os workers terminaram
                    if all(future.done() for future in futures):
                        break
            
            except KeyboardInterrupt:
                self.running = False
            
            finally:
                self.running = False
                
                # Aguardar finalização dos workers
                for future in futures:
                    try:
                        future.result(timeout=5)
                    except Exception as e:
                        self.logger.error(f"Erro ao finalizar worker: {e}")
        
        # Finalizar
        self.save_statistics()
        self.logger.info("Crawler PARALELO finalizado!")
        self.logger.info(f"Pessoas coletadas: {self.collected_count}")
        rate = self.collected_count / len(self.visited_links) if self.visited_links else 0
        self.logger.info(f"Taxa de sucesso: {rate:.2%}")

    def save_statistics(self):
        """Salva estatísticas"""
        stats = {
            'pessoas_coletadas': self.collected_count,
            'paginas_visitadas': len(self.visited_links),
            'paginas_pessoa': len(self.person_pages),
            'taxa_sucesso': self.collected_count / len(self.visited_links) if self.visited_links else 0,
            'num_workers': self.num_workers,
            'person_pages': list(self.person_pages)
        }
        
        with open(os.path.join(self.output_dir, 'estatisticas_paralelo.json'), 'w', encoding='utf-8') as f:
            json.dump(stats, f, ensure_ascii=False, indent=2)

if __name__ == "__main__":
    # Permitir configurar número de workers
    import sys
    num_workers = int(sys.argv[1]) if len(sys.argv) > 1 else 5
    
    crawler = ParallelWikipediaCrawler(num_workers=num_workers)
    crawler.run_parallel_crawler()