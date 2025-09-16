import os
import json
import re
from bs4 import BeautifulSoup
from collections import deque, defaultdict
import logging
from urllib.parse import unquote

class SixDegreesCalculator:
    def __init__(self, pages_directory="wikipedia_pessoas"):
        self.pages_dir = pages_directory
        self.person_graph = defaultdict(set)
        self.person_names = {}
        self.file_to_name = {}
        self.url_to_name = {}
        
        logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
        self.logger = logging.getLogger(__name__)
        
        self.load_all_pages()
        self.build_connection_graph()

    def sanitize_name(self, name):
        """Normaliza o nome para comparação"""
        if '%' in name:
            name = unquote(name)
        
        name = re.sub(r'[^\w\sáàâãéèêíìîóòôõúùûç]', '', name.lower().strip())
        name = re.sub(r'\s+', ' ', name)
        return name

    def load_all_pages(self):
        self.logger.info("Carregando páginas...")
        
        if not os.path.exists(self.pages_dir):
            self.logger.error(f"Diretório {self.pages_dir} não encontrado!")
            return
            
        html_files = [f for f in os.listdir(self.pages_dir) if f.endswith('.html')]
        
        for file in html_files:
            try:
                filepath = os.path.join(self.pages_dir, file)
                with open(filepath, 'r', encoding='utf-8') as f:
                    content = f.read()
                    
                soup = BeautifulSoup(content, 'html.parser')
                
                title_element = soup.find("span", {"class": "mw-page-title-main"})
                if title_element:
                    person_name = title_element.get_text(strip=True)
                else:
                    person_name = file.replace('.html', '').replace('_', ' ')
                
                normalized_name = self.sanitize_name(person_name)
                self.person_names[normalized_name] = file
                self.file_to_name[file] = person_name
                
                file_based_name = self.sanitize_name(file.replace('.html', '').replace('_', ' '))
                if file_based_name != normalized_name:
                    self.person_names[file_based_name] = file
                
            except Exception as e:
                self.logger.error(f"Erro ao processar {file}: {e}")
        
        self.logger.info(f"Carregadas {len(self.person_names)} páginas de pessoas")

    def extract_person_links(self, soup):
        """Extrai links para outras pessoas da página"""
        person_links = []
        
        try:
            content_selectors = [
                "div#mw-content-text",
                "div.mw-parser-output", 
                "div#bodyContent"
            ]
            
            content_div = None
            for selector in content_selectors:
                content_div = soup.select_one(selector)
                if content_div:
                    break
            
            if content_div:
                wiki_links = content_div.find_all("a", href=re.compile(r"^/wiki/[^:#]+$"))
                
                for link in wiki_links:
                    href = link.get('href', '')
                    link_text = link.get_text(strip=True)
                    
                    if href and link_text and len(link_text) > 1:
                        page_name = href.replace('/wiki/', '')
                        page_name = unquote(page_name).replace('_', ' ')
                        
                        normalized_page = self.sanitize_name(page_name)
                        normalized_text = self.sanitize_name(link_text)
                        
                        found_person = None
                        if normalized_page in self.person_names:
                            found_person = normalized_page
                        elif normalized_text in self.person_names:
                            found_person = normalized_text
                        else:
                            for person_name in self.person_names.keys():
                                if (normalized_text in person_name or 
                                    person_name in normalized_text or
                                    normalized_page in person_name or
                                    person_name in normalized_page):
                                    found_person = person_name
                                    break
                        
                        if found_person:
                            person_links.append(found_person)
                            
        except Exception as e:
            self.logger.error(f"Erro ao extrair links de pessoa: {e}")
            
        return list(set(person_links))

    def build_connection_graph(self):
        self.logger.info("Construindo grafo de conexões...")
        
        for filename, person_name in self.file_to_name.items():
            try:
                filepath = os.path.join(self.pages_dir, filename)
                with open(filepath, 'r', encoding='utf-8') as f:
                    content = f.read()
                    
                soup = BeautifulSoup(content, 'html.parser')
                
                mentioned_persons = self.extract_person_links(soup)
                
                normalized_current = self.sanitize_name(person_name)
                
                for mentioned_person in mentioned_persons:
                    if mentioned_person != normalized_current:
                        self.person_graph[normalized_current].add(mentioned_person)
                        
            except Exception as e:
                self.logger.error(f"Erro ao processar conexões de {filename}: {e}")
        
        total_connections = sum(len(connections) for connections in self.person_graph.values())
        nodes_with_connections = len([p for p in self.person_graph.values() if len(p) > 0])
        
        self.logger.info(f"Grafo construído: {len(self.person_names)} pessoas totais")
        self.logger.info(f"{nodes_with_connections} pessoas com conexões")
        self.logger.info(f"{total_connections} conexões totais")

    def find_person(self, query):
        """Encontra uma pessoa pelo nome (busca flexível melhorada)"""
        query_normalized = self.sanitize_name(query)
        
        if query_normalized in self.person_names:
            return query_normalized
        
        matches = []
        
        for person_name in self.person_names.keys():
            if query_normalized in person_name or person_name in query_normalized:
                matches.append(person_name)
        
        if not matches:
            query_words = query_normalized.split()
            for person_name in self.person_names.keys():
                person_words = person_name.split()
                if all(any(qword in pword for pword in person_words) for qword in query_words):
                    matches.append(person_name)
        
        if not matches and len(query_normalized) > 2:
            query_start = query_normalized[:3]
            for person_name in self.person_names.keys():
                if person_name.startswith(query_start):
                    matches.append(person_name)
        
        matches = list(dict.fromkeys(matches))
        
        if len(matches) == 1:
            return matches[0]
        elif len(matches) > 1:
            print(f"\nMúltiplas pessoas encontradas para '{query}':")
            for i, match in enumerate(matches[:10], 1):
                original_name = self.file_to_name[self.person_names[match]]
                print(f"{i}. {original_name}")
            
            if len(matches) > 10:
                print(f"... e mais {len(matches) - 10} resultados")
            
            try:
                choice = input("\nDigite o número da pessoa desejada (ou Enter para cancelar): ").strip()
                if choice.isdigit():
                    idx = int(choice) - 1
                    if 0 <= idx < min(10, len(matches)):
                        return matches[idx]
            except:
                pass
                
            return None
        
        return None

    def bfs_shortest_path(self, start_person, end_person):
        """Encontra o caminho mais curto usando BFS"""
        if start_person == end_person:
            return [start_person]
        
        if start_person not in self.person_graph:
            self.logger.warning(f"Pessoa {start_person} não tem conexões no grafo")
            return None
        
        if end_person not in self.person_names:
            self.logger.warning(f"Pessoa {end_person} não encontrada")
            return None
        
        visited = set()
        queue = deque([(start_person, [start_person])])
        visited.add(start_person)
        
        max_depth = 6
        
        while queue:
            current_person, path = queue.popleft()
            
            if len(path) > max_depth:
                continue
            
            current_connections = self.person_graph.get(current_person, set())
            
            for neighbor in current_connections:
                if neighbor == end_person:
                    return path + [neighbor]
                
                if neighbor not in visited and len(path) < max_depth:
                    visited.add(neighbor)
                    queue.append((neighbor, path + [neighbor]))
        
        return None

    def calculate_separation_degrees(self, person1_query, person2_query):
        """Calcula o grau de separação entre duas pessoas"""
        
        print(f"\nBuscando: '{person1_query}'...")
        person1 = self.find_person(person1_query)
        
        if not person1:
            return f"Primeira pessoa não encontrada: {person1_query}"
        
        print(f"Buscando: '{person2_query}'...")
        person2 = self.find_person(person2_query)
        
        if not person2:
            return f"Segunda pessoa não encontrada: {person2_query}"
        
        name1 = self.file_to_name[self.person_names[person1]]
        name2 = self.file_to_name[self.person_names[person2]]
        
        print(f"\nCalculando separação entre: {name1} → {name2}")
        
        path = self.bfs_shortest_path(person1, person2)
        
        if not path:
            reverse_path = self.bfs_shortest_path(person2, person1)
            if reverse_path:
                path = list(reversed(reverse_path))
        
        if not path:
            return f"Não há conexão entre {name1} e {name2} (dentro de 6 graus)"
        
        original_path = []
        for normalized_name in path:
            if normalized_name in self.person_names:
                original_name = self.file_to_name[self.person_names[normalized_name]]
                original_path.append(original_name)
            else:
                original_path.append(normalized_name)
        
        degrees = len(path) - 1
        
        result = f"\n{'='*50}\n"
        result += f"GRAU DE SEPARAÇÃO: {degrees}\n"
        result += f"{'='*50}\n"
        result += f"Caminho de conexão:\n\n"
        
        for i, person in enumerate(original_path):
            if i == 0:
                result += f"1. {person} (início)\n"
            elif i == len(original_path) - 1:
                result += f"{i+1}. {person} (fim)\n"
            else:
                result += f"{i+1}. {person}\n"
        
        return result

    def get_statistics(self):
        """Retorna estatísticas do grafo"""
        total_people = len(self.person_names)
        total_connections = sum(len(connections) for connections in self.person_graph.values())
        
        max_connections = 0
        most_connected = ""
        
        for person, connections in self.person_graph.items():
            if len(connections) > max_connections:
                max_connections = len(connections)
                if person in self.person_names:
                    most_connected = self.file_to_name[self.person_names[person]]
                else:
                    most_connected = person
        
        connected_people = len([p for p in self.person_graph.values() if len(p) > 0])
        avg_connections = total_connections / total_people if total_people > 0 else 0
        
        stats = f"""
{'='*50}
ESTATÍSTICAS DO GRAFO
{'='*50}
- Total de pessoas: {total_people}
- Pessoas com conexões: {connected_people}
- Total de conexões: {total_connections}
- Conexões por pessoa (média): {avg_connections:.2f}
- Pessoa mais conectada: {most_connected} ({max_connections} conexões)
{'='*50}
"""
        return stats

    def debug_person_connections(self, person_query):
        """Debug: mostra conexões de uma pessoa específica"""
        person = self.find_person(person_query)
        if not person:
            print(f"Pessoa não encontrada: {person_query}")
            return
        
        original_name = self.file_to_name[self.person_names[person]]
        connections = self.person_graph.get(person, set())
        
        print(f"\nConexões de {original_name}:")
        print(f"Total: {len(connections)} conexões")
        
        for i, conn in enumerate(sorted(connections), 1):
            if conn in self.person_names:
                conn_name = self.file_to_name[self.person_names[conn]]
                print(f"{i}. {conn_name}")
            else:
                print(f"{i}. {conn} (não encontrado)")

    def interactive_mode(self):
        """Modo interativo para calcular graus de separação"""
        print("=== CALCULADORA DE 6 GRAUS DE SEPARAÇÃO ===")
        print(self.get_statistics())
        print("\nComandos especiais:")
        print("- 'sair' para encerrar")
        print("- 'debug <nome>' para ver conexões de uma pessoa")
        print("- 'stats' para ver estatísticas")
        
        while True:
            try:
                print("\n" + "="*50)
                person1 = input("Digite o nome da primeira pessoa: ").strip()
                
                if person1.lower() == 'sair':
                    break
                elif person1.lower() == 'stats':
                    print(self.get_statistics())
                    continue
                elif person1.lower().startswith('debug '):
                    debug_name = person1[6:].strip()
                    self.debug_person_connections(debug_name)
                    continue
                
                person2 = input("Digite o nome da segunda pessoa: ").strip()
                
                if person2.lower() == 'sair':
                    break
                
                result = self.calculate_separation_degrees(person1, person2)
                print(result)
                
            except KeyboardInterrupt:
                print("\nEncerrando...")
                break
            except Exception as e:
                print(f"Erro: {e}")
                self.logger.error(f"Erro no modo interativo: {e}", exc_info=True)

if __name__ == "__main__":
    calculator = SixDegreesCalculator()
    calculator.interactive_mode()