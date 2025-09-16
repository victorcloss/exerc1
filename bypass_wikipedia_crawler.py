import requests
from bs4 import BeautifulSoup
import time
import re
import os
import json
import logging
import random
from urllib.parse import urljoin

class BypassWikipediaCrawler:
    def __init__(self, target_count=50):
        self.base_url = "https://pt.wikipedia.org/"
        self.target_count = target_count
        self.collected_count = 0
        self.visited_links = set()
        self.person_pages = []
        
        # Setup de sessão com rotação de headers
        self.sessions = []
        self.create_sessions()
        self.current_session = 0
        
        # Diretório de saída
        self.output_dir = "wikipedia_pessoas"
        if not os.path.exists(self.output_dir):
            os.makedirs(self.output_dir)
        
        # Logging
        logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(message)s')
        self.logger = logging.getLogger(__name__)
        
        # Lista de pessoas famosas para teste
        self.famous_people = [
            "wiki/Pelé", "wiki/Caetano_Veloso", "wiki/Getúlio_Vargas",
            "wiki/Machado_de_Assis", "wiki/Tom_Jobim", "wiki/Chico_Buarque",
            "wiki/Gilberto_Gil", "wiki/Roberto_Carlos_(cantor)", "wiki/Ayrton_Senna",
            "wiki/Xuxa", "wiki/Gisele_Bündchen", "wiki/Ronaldinho_Gaúcho",
            "wiki/Fernando_Henrique_Cardoso", "wiki/Luiz_Inácio_Lula_da_Silva",
            "wiki/Dilma_Rousseff", "wiki/Tarcísio_Meira", "wiki/Regina_Duarte",
            "wiki/Fernanda_Montenegro", "wiki/Lima_Barreto", "wiki/Clarice_Lispector",
            "wiki/Oscar_Niemeyer", "wiki/Carmen_Miranda", "wiki/Elis_Regina",
            "wiki/Milton_Nascimento", "wiki/Maria_Bethânia", "wiki/Daniela_Mercury",
            "wiki/Ivete_Sangalo", "wiki/Sandy_Leah", "wiki/Junior_Lima",
            "wiki/Carla_Perez", "wiki/Gugu_Liberato", "wiki/Silvio_Santos",
            "wiki/Fausto_Silva", "wiki/Luciano_Huck", "wiki/Ana_Maria_Braga",
            "wiki/Hebe_Camargo", "wiki/Jô_Soares", "wiki/Pedro_Bial",
            "wiki/William_Bonner", "wiki/Fátima_Bernardes", "wiki/Galvão_Bueno",
            "wiki/Ronaldo_Nazário", "wiki/Rivaldo", "wiki/Kaká", "wiki/Romário",
            "wiki/Bebeto", "wiki/Zico", "wiki/Garrincha", "wiki/Tostão",
            "wiki/Carlos_Alberto_Torres", "wiki/Sócrates_(futebolista)",
            "wiki/Nelson_Mandela", "wiki/Albert_Einstein", "wiki/Leonardo_da_Vinci",
            "wiki/Pablo_Picasso", "wiki/Vincent_van_Gogh", "wiki/Mozart",
            "wiki/Beethoven", "wiki/William_Shakespeare", "wiki/Charles_Darwin",
            "wiki/Isaac_Newton", "wiki/Marie_Curie", "wiki/Nikola_Tesla"
        ]

    def create_sessions(self):
        """Cria múltiplas sessões com diferentes headers"""
        user_agents = [
            'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36',
            'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36',
            'Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:89.0) Gecko/20100101 Firefox/89.0',
            'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/14.1.1 Safari/605.1.15',
            'Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'
        ]
        
        for i, ua in enumerate(user_agents):
            session = requests.Session()
            session.headers.update({
                'User-Agent': ua,
                'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8',
                'Accept-Language': 'pt-BR,pt;q=0.9,en;q=0.8',
                'Accept-Encoding': 'gzip, deflate, br',
                'DNT': '1',
                'Connection': 'keep-alive',
                'Upgrade-Insecure-Requests': '1',
                'Sec-Fetch-Dest': 'document',
                'Sec-Fetch-Mode': 'navigate',
                'Sec-Fetch-Site': 'none',
                'Cache-Control': 'max-age=0'
            })
            self.sessions.append(session)

    def get_session(self):
        """Rotaciona entre sessões"""
        session = self.sessions[self.current_session]
        self.current_session = (self.current_session + 1) % len(self.sessions)
        return session

    def make_request(self, url, max_retries=3):
        """Faz requisição com retry e diferentes estratégias"""
        for attempt in range(max_retries):
            try:
                session = self.get_session()
                
                # Pausa aleatória para parecer humano
                time.sleep(random.uniform(1.0, 3.0))
                
                response = session.get(url, timeout=15)
                
                if response.status_code == 200:
                    return response
                elif response.status_code == 403:
                    self.logger.warning(f"Bloqueado (403) na tentativa {attempt + 1}")
                    if attempt < max_retries - 1:
                        # Pausa mais longa antes de tentar novamente
                        time.sleep(random.uniform(5.0, 10.0))
                elif response.status_code == 429:
                    self.logger.warning(f"Rate limited (429) na tentativa {attempt + 1}")
                    if attempt < max_retries - 1:
                        time.sleep(random.uniform(10.0, 20.0))
                else:
                    self.logger.warning(f"Status {response.status_code} na tentativa {attempt + 1}")
                
            except requests.exceptions.RequestException as e:
                self.logger.error(f"Erro de conexão na tentativa {attempt + 1}: {e}")
                if attempt < max_retries - 1:
                    time.sleep(random.uniform(2.0, 5.0))
        
        return None

    def test_connection(self):
        """Testa se consegue acessar Wikipedia"""
        print("TESTANDO CONEXÃO COM BYPASS...")
        print("=" * 40)
        
        test_url = "https://pt.wikipedia.org/wiki/Brasil"
        response = self.make_request(test_url)
        
        if response:
            print(f"✅ Conexão OK (Status: {response.status_code})")
            soup = BeautifulSoup(response.content, 'html.parser')
            title = soup.find("span", {"class": "mw-page-title-main"})
            if title:
                print(f"✅ Parsing OK - Título: {title.get_text(strip=True)}")
                return True
            else:
                print("❌ Parsing falhou - estrutura mudou")
                return False
        else:
            print("❌ Conexão falhou")
            return False

    def is_person_simple(self, soup, url):
        """Detecção simples de pessoas"""
        try:
            # Título
            title_elem = soup.find("span", {"class": "mw-page-title-main"})
            if not title_elem:
                return False, ""
            
            title = title_elem.get_text(strip=True)
            
            # Verificar se há datas de nascimento/morte no título
            if re.search(r'\(\d{4}[-–]\d{4}\)', title) or re.search(r'\(\d{4}[-–]\)', title):
                return True, title
            
            # Verificar infobox
            infobox = soup.find("table", {"class": "infobox"})
            if not infobox:
                return False, title
            
            infobox_text = infobox.get_text().lower()
            
            # Campos que indicam pessoa
            person_indicators = [
                'nascimento', 'nasceu', 'morte', 'morreu',
                'cônjuge', 'esposa', 'marido', 'filhos',
                'ocupação', 'profissão', 'atividade'
            ]
            
            found_indicators = sum(1 for indicator in person_indicators if indicator in infobox_text)
            
            if found_indicators >= 2:
                return True, title
            
            # Verificação adicional no primeiro parágrafo
            if found_indicators == 1:
                first_para = soup.find("p")
                if first_para:
                    para_text = first_para.get_text().lower()[:300]
                    bio_patterns = [
                        r'é um (ator|cantor|político|escritor|jogador|artista)',
                        r'é uma (atriz|cantora|política|escritora|jogadora|artista)',
                        r'foi um (ator|cantor|político|escritor|jogador|artista)',
                        r'foi uma (atriz|cantora|política|escritora|jogadora|artista)'
                    ]
                    
                    for pattern in bio_patterns:
                        if re.search(pattern, para_text):
                            return True, title
            
            return False, title
            
        except Exception as e:
            self.logger.error(f"Erro ao verificar {url}: {e}")
            return False, ""

    def save_page(self, content, title):
        """Salva página"""
        try:
            safe_title = re.sub(r'[<>:"/\\|?*]', '_', title)[:80]
            filename = f"{safe_title}.html"
            filepath = os.path.join(self.output_dir, filename)
            
            with open(filepath, 'w', encoding='utf-8') as f:
                f.write(content)
            
            return True
        except Exception as e:
            self.logger.error(f"Erro ao salvar {title}: {e}")
            return False

    def collect_people(self):
        """Coleta pessoas da lista conhecida"""
        self.logger.info(f"Iniciando coleta de {self.target_count} pessoas")
        self.logger.info("Usando lista de pessoas famosas com bypass de bloqueios...")
        
        # Embaralhar lista para variar
        people_list = self.famous_people.copy()
        random.shuffle(people_list)
        
        for url_path in people_list:
            if self.collected_count >= self.target_count:
                break
            
            full_url = urljoin(self.base_url, url_path)
            
            if full_url in self.visited_links:
                continue
            
            self.logger.info(f"Testando ({len(self.visited_links) + 1}): {url_path}")
            
            response = self.make_request(full_url)
            
            if not response:
                self.logger.error(f"Falha ao acessar: {url_path}")
                continue
            
            self.visited_links.add(full_url)
            soup = BeautifulSoup(response.content, 'html.parser')
            
            is_person, title = self.is_person_simple(soup, full_url)
            
            if is_person:
                if self.save_page(response.text, title):
                    self.collected_count += 1
                    self.person_pages.append({
                        'url': full_url,
                        'title': title
                    })
                    self.logger.info(f"✅ PESSOA SALVA ({self.collected_count}/{self.target_count}): {title}")
                else:
                    self.logger.error(f"Erro ao salvar: {title}")
            else:
                self.logger.info(f"❌ NÃO É PESSOA: {title}")
        
        # Salvar estatísticas
        self.save_stats()
        
        self.logger.info("COLETA FINALIZADA!")
        self.logger.info(f"Pessoas coletadas: {self.collected_count}")
        if self.visited_links:
            success_rate = self.collected_count / len(self.visited_links) * 100
            self.logger.info(f"Taxa de sucesso: {success_rate:.1f}%")

    def save_stats(self):
        """Salva estatísticas"""
        stats = {
            'pessoas_coletadas': self.collected_count,
            'paginas_visitadas': len(self.visited_links),
            'taxa_sucesso': self.collected_count / len(self.visited_links) if self.visited_links else 0,
            'person_pages': self.person_pages
        }
        
        with open(os.path.join(self.output_dir, 'estatisticas.json'), 'w', encoding='utf-8') as f:
            json.dump(stats, f, ensure_ascii=False, indent=2)

def main():
    print("CRAWLER COM BYPASS DE BLOQUEIOS WIKIPEDIA")
    print("=" * 50)
    
    # Permitir configurar target
    import sys
    target = 50
    if len(sys.argv) > 1:
        try:
            target = int(sys.argv[1])
        except ValueError:
            print("Uso: python bypass_crawler.py [numero_pessoas]")
            return
    
    crawler = BypassWikipediaCrawler(target_count=target)
    
    # Testar conexão primeiro
    if not crawler.test_connection():
        print("❌ Não foi possível estabelecer conexão com bypass")
        print("\nTentativas de solução:")
        print("1. Verificar se há proxy/firewall bloqueando")
        print("2. Tentar com VPN")
        print("3. Aguardar algumas horas e tentar novamente")
        return
    
    print("\n🚀 INICIANDO COLETA...")
    crawler.collect_people()

if __name__ == "__main__":
    main()