#!/usr/bin/env python3
"""
Script para testar e comparar diferentes versões do crawler
"""

import time
import json
import os
import subprocess
import sys
from datetime import datetime

class CrawlerBenchmark:
    def __init__(self):
        self.results = {}
        self.test_target = 50  # Número menor para testes rápidos
        
    def run_test(self, script_name, description, timeout=600):
        """Executa um teste de crawler"""
        print(f"\n{'='*60}")
        print(f"TESTANDO: {description}")
        print(f"Script: {script_name}")
        print(f"Meta: {self.test_target} pessoas")
        print(f"Timeout: {timeout} segundos")
        print(f"{'='*60}")
        
        start_time = time.time()
        
        try:
            # Modificar temporariamente o target no script
            self.modify_target_count(script_name, self.test_target)
            
            # Executar o script
            result = subprocess.run([
                sys.executable, script_name
            ], timeout=timeout, capture_output=True, text=True)
            
            end_time = time.time()
            elapsed = end_time - start_time
            
            # Analisar resultados
            stats = self.analyze_results(script_name, elapsed)
            stats['stdout'] = result.stdout[-500:] if result.stdout else ""  # Últimas 500 chars
            stats['stderr'] = result.stderr[-500:] if result.stderr else ""
            stats['return_code'] = result.returncode
            
            self.results[script_name] = stats
            
            print(f"\nRESULTADO: {description}")
            print(f"Tempo: {elapsed:.1f}s")
            print(f"Pessoas coletadas: {stats.get('pessoas_coletadas', 0)}")
            print(f"Taxa: {stats.get('taxa_sucesso', 0):.2%}")
            print(f"Pessoas/min: {stats.get('pessoas_por_minuto', 0):.1f}")
            
        except subprocess.TimeoutExpired:
            print(f"TIMEOUT: {description} não terminou em {timeout} segundos")
            self.results[script_name] = {
                'timeout': True,
                'elapsed_time': timeout,
                'pessoas_coletadas': 0
            }
        except Exception as e:
            print(f"ERRO: {e}")
            self.results[script_name] = {
                'error': str(e),
                'elapsed_time': 0,
                'pessoas_coletadas': 0
            }
        finally:
            # Restaurar target original
            self.restore_target_count(script_name)
    
    def modify_target_count(self, script_name, new_target):
        """Modifica temporariamente o target_count no script"""
        try:
            with open(script_name, 'r', encoding='utf-8') as f:
                content = f.read()
            
            # Backup
            with open(f"{script_name}.backup", 'w', encoding='utf-8') as f:
                f.write(content)
            
            # Modificar target_count
            import re
            modified = re.sub(
                r'self\.target_count\s*=\s*\d+',
                f'self.target_count = {new_target}',
                content
            )
            
            with open(script_name, 'w', encoding='utf-8') as f:
                f.write(modified)
                
        except Exception as e:
            print(f"Erro ao modificar {script_name}: {e}")
    
    def restore_target_count(self, script_name):
        """Restaura o target_count original"""
        try:
            backup_file = f"{script_name}.backup"
            if os.path.exists(backup_file):
                with open(backup_file, 'r', encoding='utf-8') as f:
                    content = f.read()
                
                with open(script_name, 'w', encoding='utf-8') as f:
                    f.write(content)
                
                os.remove(backup_file)
        except Exception as e:
            print(f"Erro ao restaurar {script_name}: {e}")
    
    def analyze_results(self, script_name, elapsed_time):
        """Analisa os resultados de um teste"""
        stats = {
            'elapsed_time': elapsed_time,
            'pessoas_coletadas': 0,
            'paginas_visitadas': 0,
            'taxa_sucesso': 0,
            'pessoas_por_minuto': 0
        }
        
        # Procurar por arquivo de estatísticas
        stats_files = [
            'wikipedia_pessoas/estatisticas.json',
            'wikipedia_pessoas/estatisticas_otimizadas.json',
            'wikipedia_pessoas/estatisticas_paralelo.json'
        ]
        
        for stats_file in stats_files:
            if os.path.exists(stats_file):
                try:
                    with open(stats_file, 'r', encoding='utf-8') as f:
                        file_stats = json.load(f)
                    
                    stats['pessoas_coletadas'] = file_stats.get('pessoas_coletadas', 0)
                    stats['paginas_visitadas'] = file_stats.get('paginas_visitadas', 0)
                    stats['taxa_sucesso'] = file_stats.get('taxa_sucesso', 0)
                    
                    if elapsed_time > 0:
                        stats['pessoas_por_minuto'] = (stats['pessoas_coletadas'] / elapsed_time) * 60
                    
                    break
                    
                except Exception as e:
                    print(f"Erro ao ler {stats_file}: {e}")
        
        return stats
    
    def run_benchmark_suite(self):
        """Executa suite completa de benchmarks"""
        print("INICIANDO BENCHMARK DOS CRAWLERS")
        print("="*60)
        
        # Limpar diretório de resultados
        if os.path.exists('wikipedia_pessoas'):
            import shutil
            shutil.rmtree('wikipedia_pessoas')
        
        tests = [
            ('wiki_crawler.py', 'Crawler Original', 300),
            ('optimized_wiki_crawler.py', 'Crawler Otimizado', 300),
            ('parallel_wiki_crawler.py', 'Crawler Paralelo', 300),
        ]
        
        for script_name, description, timeout in tests:
            if os.path.exists(script_name):
                # Limpar resultados anteriores
                if os.path.exists('wikipedia_pessoas'):
                    import shutil
                    shutil.rmtree('wikipedia_pessoas')
                
                self.run_test(script_name, description, timeout)
                time.sleep(5)  # Pausa entre testes
            else:
                print(f"AVISO: {script_name} não encontrado, pulando teste")
        
        # Gerar relatório final
        self.generate_report()
    
    def generate_report(self):
        """Gera relatório comparativo final"""
        print(f"\n{'='*80}")
        print("RELATÓRIO FINAL - COMPARAÇÃO DOS CRAWLERS")
        print(f"{'='*80}")
        
        if not self.results:
            print("Nenhum resultado para comparar")
            return
        
        # Cabeçalho da tabela
        print(f"{'Crawler':<25} {'Tempo(s)':<10} {'Pessoas':<10} {'Taxa%':<8} {'P/min':<8} {'Status':<15}")
        print("-" * 80)
        
        # Dados de cada crawler
        for script_name, stats in self.results.items():
            name = script_name.replace('.py', '').replace('_', ' ').title()[:24]
            
            if stats.get('timeout'):
                status = "TIMEOUT"
                tempo = f"{stats['elapsed_time']:.0f}"
                pessoas = "0"
                taxa = "0.00"
                p_min = "0.0"
            elif stats.get('error'):
                status = "ERRO"
                tempo = "N/A"
                pessoas = "0"
                taxa = "0.00"
                p_min = "0.0"
            else:
                status = "OK"
                tempo = f"{stats['elapsed_time']:.0f}"
                pessoas = str(stats['pessoas_coletadas'])
                taxa = f"{stats['taxa_sucesso']*100:.1f}"
                p_min = f"{stats['pessoas_por_minuto']:.1f}"
            
            print(f"{name:<25} {tempo:<10} {pessoas:<10} {taxa:<8} {p_min:<8} {status:<15}")
        
        # Encontrar o melhor
        best_crawler = None
        best_score = 0
        
        for script_name, stats in self.results.items():
            if not stats.get('timeout') and not stats.get('error'):
                # Score baseado em pessoas/minuto
                score = stats.get('pessoas_por_minuto', 0)
                if score > best_score:
                    best_score = score
                    best_crawler = script_name
        
        if best_crawler:
            print(f"\n🏆 VENCEDOR: {best_crawler}")
            print(f"   Melhor taxa: {best_score:.1f} pessoas por minuto")
        
        # Salvar relatório
        report_data = {
            'timestamp': datetime.now().isoformat(),
            'test_target': self.test_target,
            'results': self.results,
            'best_crawler': best_crawler,
            'best_score': best_score
        }
        
        with open('benchmark_results.json', 'w', encoding='utf-8') as f:
            json.dump(report_data, f, ensure_ascii=False, indent=2)
        
        print(f"\nRelatório salvo em: benchmark_results.json")
        
        # Recomendações
        print(f"\n{'='*80}")
        print("RECOMENDAÇÕES:")
        
        if best_crawler:
            if 'parallel' in best_crawler:
                print("• Use o crawler paralelo para máxima velocidade")
                print("• Ajuste o número de workers conforme sua conexão")
            elif 'optimized' in best_crawler:
                print("• Use o crawler otimizado para boa performance com estabilidade")
            else:
                print("• O crawler original pode ser suficiente para seus dados")
        
        print("• Monitore a taxa de sucesso além da velocidade")
        print("• Considere executar por mais tempo para resultados mais estáveis")

def main():
    """Função principal"""
    print("Benchmark dos Crawlers Wikipedia")
    print("Este teste irá comparar as diferentes versões do crawler")
    print(f"Meta de teste: 50 pessoas por crawler")
    print()
    
    response = input("Deseja continuar? (s/n): ").lower()
    if response != 's':
        print("Teste cancelado")
        return
    
    benchmark = CrawlerBenchmark()
    benchmark.run_benchmark_suite()

if __name__ == "__main__":
    main()