#!/usr/bin/env python3
"""
Script de diagnóstico rápido para identificar problemas
"""

import requests
from bs4 import BeautifulSoup
import time
import sys
import traceback

def test_basic_connection():
    """Testa conexão básica com Wikipedia"""
    print("1. TESTANDO CONEXÃO BÁSICA...")
    try:
        response = requests.get("https://pt.wikipedia.org/wiki/Brasil", timeout=10)
        if response.status_code == 200:
            print("   ✅ Conexão OK")
            return True
        else:
            print(f"   ❌ Status code: {response.status_code}")
            return False
    except Exception as e:
        print(f"   ❌ Erro de conexão: {e}")
        return False

def test_page_parsing():
    """Testa parsing de uma página conhecida"""
    print("2. TESTANDO PARSING DE PÁGINA...")
    try:
        response = requests.get("https://pt.wikipedia.org/wiki/Pelé", timeout=10)
        soup = BeautifulSoup(response.content, 'html.parser')
        
        # Verificar título
        title = soup.find("span", {"class": "mw-page-title-main"})
        if title:
            print(f"   ✅ Título encontrado: {title.get_text(strip=True)}")
        else:
            print("   ❌ Título não encontrado")
            return False
        
        # Verificar infobox
        infobox = soup.find("table", {"class": "infobox"})
        if infobox:
            print("   ✅ Infobox encontrada")
            infobox_text = infobox.get_text().lower()
            if 'nascimento' in infobox_text:
                print("   ✅ Campo 'nascimento' encontrado")
            else:
                print("   ⚠️  Campo 'nascimento' não encontrado")
        else:
            print("   ❌ Infobox não encontrada")
            return False
        
        return True
        
    except Exception as e:
        print(f"   ❌ Erro no parsing: {e}")
        traceback.print_exc()
        return False

def test_person_detection():
    """Testa detecção de pessoa numa página conhecida"""
    print("3. TESTANDO DETECÇÃO DE PESSOA...")
    
    def is_person_test(soup):
        """Função de teste simples"""
        try:
            # Título
            title_elem = soup.find("span", {"class": "mw-page-title-main"})
            if not title_elem:
                return False, "Sem título"
            
            title = title_elem.get_text(strip=True)
            
            # Infobox
            infobox = soup.find("table", {"class": "infobox"})
            if not infobox:
                return False, title
            
            infobox_text = infobox.get_text().lower()
            
            # Campos de pessoa
            person_fields = ['nascimento', 'morte', 'cônjuge', 'ocupação', 'profissão']
            found = sum(1 for field in person_fields if field in infobox_text)
            
            return found >= 2, title
            
        except Exception as e:
            return False, f"Erro: {e}"
    
    test_cases = [
        ("https://pt.wikipedia.org/wiki/Pelé", True, "Pessoa famosa"),
        ("https://pt.wikipedia.org/wiki/Brasil", False, "País (não pessoa)"),
        ("https://pt.wikipedia.org/wiki/Caetano_Veloso", True, "Cantor famoso"),
        ("https://pt.wikipedia.org/wiki/São_Paulo", False, "Cidade (não pessoa)")
    ]
    
    correct = 0
    total = len(test_cases)
    
    for url, expected, description in test_cases:
        try:
            response = requests.get(url, timeout=10)
            soup = BeautifulSoup(response.content, 'html.parser')
            
            is_person, title = is_person_test(soup)
            
            if is_person == expected:
                status = "✅"
                correct += 1
            else:
                status = "❌"
            
            expected_str = "PESSOA" if expected else "NÃO PESSOA"
            result_str = "PESSOA" if is_person else "NÃO PESSOA"
            
            print(f"   {status} {description}")
            print(f"      Título: {title}")
            print(f"      Esperado: {expected_str} | Resultado: {result_str}")
            
            time.sleep(0.5)
            
        except Exception as e:
            print(f"   ❌ Erro ao testar {description}: {e}")
    
    accuracy = (correct / total) * 100
    print(f"   📊 Precisão: {accuracy:.1f}% ({correct}/{total})")
    
    return accuracy >= 75

def test_file_operations():
    """Testa operações de arquivo"""
    print("4. TESTANDO OPERAÇÕES DE ARQUIVO...")
    
    try:
        import os
        
        # Criar diretório
        test_dir = "test_wikipedia"
        if not os.path.exists(test_dir):
            os.makedirs(test_dir)
            print("   ✅ Diretório criado")
        else:
            print("   ✅ Diretório já existe")
        
        # Escrever arquivo
        test_file = os.path.join(test_dir, "teste.html")
        with open(test_file, 'w', encoding='utf-8') as f:
            f.write("<html><body>Teste</body></html>")
        print("   ✅ Arquivo criado")
        
        # Ler arquivo
        with open(test_file, 'r', encoding='utf-8') as f:
            content = f.read()
            if "Teste" in content:
                print("   ✅ Arquivo lido corretamente")
            else:
                print("   ❌ Conteúdo incorreto")
                return False
        
        # Limpar
        os.remove(test_file)
        os.rmdir(test_dir)
        print("   ✅ Arquivos limpos")
        
        return True
        
    except Exception as e:
        print(f"   ❌ Erro nas operações de arquivo: {e}")
        return False

def test_json_operations():
    """Testa operações JSON"""
    print("5. TESTANDO OPERAÇÕES JSON...")
    
    try:
        import json
        import os
        
        test_data = {
            'pessoas_coletadas': 5,
            'taxa_sucesso': 0.85,
            'person_pages': ['https://pt.wikipedia.org/wiki/Pelé']
        }
        
        # Criar diretório temporário
        test_dir = "test_json"
        if not os.path.exists(test_dir):
            os.makedirs(test_dir)
        
        # Escrever JSON
        json_file = os.path.join(test_dir, "stats.json")
        with open(json_file, 'w', encoding='utf-8') as f:
            json.dump(test_data, f, ensure_ascii=False, indent=2)
        print("   ✅ JSON escrito")
        
        # Ler JSON
        with open(json_file, 'r', encoding='utf-8') as f:
            loaded_data = json.load(f)
            if loaded_data['pessoas_coletadas'] == 5:
                print("   ✅ JSON lido corretamente")
            else:
                print("   ❌ Dados JSON incorretos")
                return False
        
        # Limpar
        os.remove(json_file)
        os.rmdir(test_dir)
        print("   ✅ Arquivos JSON limpos")
        
        return True
        
    except Exception as e:
        print(f"   ❌ Erro nas operações JSON: {e}")
        return False

def main():
    """Executa todos os testes de diagnóstico"""
    print("🔍 DIAGNÓSTICO RÁPIDO DOS CRAWLERS")
    print("=" * 50)
    
    tests = [
        ("Conexão", test_basic_connection),
        ("Parsing", test_page_parsing), 
        ("Detecção", test_person_detection),
        ("Arquivos", test_file_operations),
        ("JSON", test_json_operations)
    ]
    
    results = {}
    
    for test_name, test_func in tests:
        print()
        try:
            results[test_name] = test_func()
        except Exception as e:
            print(f"   💥 ERRO CRÍTICO em {test_name}: {e}")
            results[test_name] = False
        
        time.sleep(0.5)
    
    # Relatório final
    print("\n" + "=" * 50)
    print("📋 RELATÓRIO DE DIAGNÓSTICO")
    print("=" * 50)
    
    all_passed = True
    for test_name, passed in results.items():
        status = "✅ PASSOU" if passed else "❌ FALHOU"
        print(f"{test_name:<12}: {status}")
        if not passed:
            all_passed = False
    
    print("=" * 50)
    
    if all_passed:
        print("🎉 TODOS OS TESTES PASSARAM!")
        print("O problema pode estar na lógica específica dos crawlers.")
        print("\nPróximos passos:")
        print("1. Execute: python debug_crawler.py 10")
        print("2. Verifique se coleta pelo menos algumas pessoas")
        print("3. Se funcionar, use esse como base")
    else:
        print("⚠️  ALGUNS TESTES FALHARAM!")
        print("Corrija os problemas indicados antes de usar os crawlers.")
        print("\nProblemas comuns:")
        print("- Conexão de internet instável")
        print("- Bloqueio por firewall/proxy")
        print("- Estrutura da Wikipedia mudou")
        print("- Problemas de permissão de arquivo")
    
    print("\n🔧 Se tudo passou mas crawlers não funcionam:")
    print("Execute: python debug_crawler.py 5")

if __name__ == "__main__":
    main()