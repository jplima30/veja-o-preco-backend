import os
import shutil
import re
import sys
from datetime import datetime

# Garante que o script consiga importar outros scripts na mesma pasta
sys.path.append(os.path.dirname(__file__))

# Tenta importar o EasyOCR. Se não estiver instalado, avisa o usuário.
try:
    import easyocr
    OCR_DISPONIVEL = True
except ImportError:
    OCR_DISPONIVEL = False

# Configurações
BASE_DIR = os.path.join(os.path.dirname(__file__), "..", "auditoria_visual")
PASTA_FILTRADA = os.path.join(BASE_DIR, "TRIAGEM_DE_OFERTAS")
ARQUIVO_LIMPEZA = os.path.join(BASE_DIR, ".last_cleanup")

def realizar_faxina_semanal():
    """
    Apaga as fotos brutas da semana se for Sábado após as 12h ou Domingo.
    """
    agora = datetime.now()
    dia_semana = agora.weekday() # 5 = Sábado, 6 = Domingo
    hora = agora.hour
    
    # Identificador da semana atual (Ano-Semana)
    semana_atual = agora.strftime("%Y-%U")
    
    # Verifica se já limpamos esta semana
    ultima_limpeza = ""
    if os.path.exists(ARQUIVO_LIMPEZA):
        with open(ARQUIVO_LIMPEZA, "r") as f:
            ultima_limpeza = f.read().strip()
            
    # Gatilho: Sábado >= 12h OU Domingo
    if (dia_semana == 5 and hora >= 12) or dia_semana > 5:
        if ultima_limpeza != semana_atual:
            print(f"\n🧹 [FAXINA SEMANAL] Sábado detectado. Limpando fotos da semana...")
            
            # 1. Limpa as fotos brutas da Auditoria
            print(f"  📂 Faxinando pastas de Auditoria...")
            for item in os.listdir(BASE_DIR):
                item_path = os.path.join(BASE_DIR, item)
                if os.path.isdir(item_path) and re.match(r"\d{4}-\d{2}-\d{2}", item):
                    try:
                        shutil.rmtree(item_path)
                        print(f"    🗑️ Removida: {item}")
                    except Exception as e:
                        print(f"    ⚠️ Erro ao remover {item}: {e}")
            
            # 2. Limpa os resultados da Triagem (Fotos filtradas)
            if os.path.exists(PASTA_FILTRADA):
                print(f"  📂 Faxinando pastas de Triagem...")
                for item in os.listdir(PASTA_FILTRADA):
                    item_path = os.path.join(PASTA_FILTRADA, item)
                    if os.path.isdir(item_path) and re.match(r"\d{4}-\d{2}-\d{2}", item):
                        try:
                            shutil.rmtree(item_path)
                            print(f"    🗑️ Triagem removida: {item}")
                        except Exception as e:
                            print(f"    ⚠️ Erro ao remover triagem {item}: {e}")
            
            # Registra que a limpeza da semana foi feita
            with open(ARQUIVO_LIMPEZA, "w") as f:
                f.write(semana_atual)
            print("✨ Faxina concluída. Disco limpo!\n")

# Configurações de Sensibilidade
TAMANHO_MINIMO_FONTE = 0.04  # Texto deve ter pelo menos 4% da altura da imagem
CONFIANCA_MINIMA = 0.3      # Confiança mínima do OCR

# Padrões mais rigorosos para PREÇOS REAIS (ex: R$ 19,90 ou 19,90)
PADRAO_PRECO_STRICT = r"(\d+[\.,]\d{2})" 
# Padrões para DATAS e VALIDADE (ex: 10/10 ou VALIDO ATE)
PADRAO_VALIDADE = r"(\d{2}/\d{2})"
PALAVRAS_CHAVE_URGENCIA = [
    "OFERTA RELAMPAGO", "OFERTA DA SEMANA", "SO HOJE", 
    "VALIDO ATE", "VALIDO DE", "VALIDADE", "PERIODO"
]

def extrair_data_hoje(janela=None):
    hoje = datetime.now()
    dias_semana = ["Segunda", "Terca", "Quarta", "Quinta", "Sexta", "Sabado", "Domingo"]
    nome_dia = dias_semana[hoje.weekday()]
    
    data_base = f"{hoje.strftime('%Y-%m-%d')}_{nome_dia}"
    
    # Se não houver janela, assume 'manual'
    if not janela:
        janela = "manual"
        
    # Só adiciona 'h' se for um número (janela de horário)
    subpasta = f"{janela}h" if str(janela).isdigit() else str(janela)
    return os.path.join(data_base, subpasta)

def limpar_pastas_orfas(caminho_dia):
    """
    Move pastas de lojas que estão na raiz da pasta do dia (órfãs) 
    para dentro da subpasta 'manual', mantendo a organização.
    """
    if not os.path.exists(caminho_dia):
        return
        
    pastas_protegidas = ["10h", "14h", "manual"]
    pasta_manual = os.path.join(caminho_dia, "manual")
    os.makedirs(pasta_manual, exist_ok=True)
    
    for item in os.listdir(caminho_dia):
        item_path = os.path.join(caminho_dia, item)
        # Se for um diretório e não for uma das pastas de janela protegidas
        if os.path.isdir(item_path) and item not in pastas_protegidas:
            # Se o item for TRIAGEM_DE_OFERTAS (que pode estar no root do BASE_DIR, mas não dentro do dia)
            # mas aqui estamos dentro de caminho_dia, então TRIAGEM_DE_OFERTAS não deveria estar aqui.
            print(f"🧹 [ORGANIZADOR] Movendo pasta órfã '{item}' para 'manual'...")
            try:
                destino = os.path.join(pasta_manual, item)
                if os.path.exists(destino):
                    for subitem in os.listdir(item_path):
                        shutil.move(os.path.join(item_path, subitem), os.path.join(destino, subitem))
                    os.rmdir(item_path)
                else:
                    shutil.move(item_path, destino)
            except Exception as e:
                print(f"  ⚠️ Erro ao mover {item}: {e}")

def analisar_imagem(reader, caminho_imagem):
    """
    Lógica de Decisão: O PREÇO é mandatório.
    Aprovado se: (Tem Preço) E (Preço é Grande OU Tem Urgência/Data)
    """
    try:
        from PIL import Image
        with Image.open(caminho_imagem) as img_file:
            width, height = img_file.size

        resultados = reader.readtext(caminho_imagem, detail=1)
        
        achou_preco = False
        achou_urgencia_ou_data = False
        preco_e_grande = False
        texto_extraido = []

        for (bbox, text, conf) in resultados:
            if conf < CONFIANCA_MINIMA:
                continue

            text_upper = text.upper()
            h_texto = bbox[2][1] - bbox[0][1]
            proporcao = h_texto / height

            # 1. Busca por PREÇO (Obrigatório)
            if re.search(PADRAO_PRECO_STRICT, text_upper):
                achou_preco = True
                texto_extraido.append(text)
                if proporcao >= TAMANHO_MINIMO_FONTE:
                    preco_e_grande = True

            # 2. Busca por URGÊNCIA ou DATA (Validador)
            for k in PALAVRAS_CHAVE_URGENCIA:
                if k in text_upper:
                    achou_urgencia_ou_data = True
                    texto_extraido.append(text)
                    break
            
            if re.search(PADRAO_VALIDADE, text_upper):
                achou_urgencia_ou_data = True
                texto_extraido.append(text)

        # DECISÃO FINAL
        # Só aprovamos se tiver preço E (for grande OU tiver contexto de urgência/validade)
        if achou_preco and (preco_e_grande or achou_urgencia_ou_data):
            return True, " | ".join(texto_extraido)
        
        return False, ""
    except Exception as e:
        print(f"      ⚠️ Erro ao analisar {os.path.basename(caminho_imagem)}: {e}")
        return False, ""

def iniciar_triagem(janela=None, data_teste=None):
    if not OCR_DISPONIVEL:
        print("❌ EasyOCR não encontrado. Instale com: pip install easyocr")
        return

    # 1. Realiza faxina de sábado se necessário
    realizar_faxina_semanal()

    # Se a janela não foi passada, tenta descobrir pelo horário atual
    if not janela:
        agora = datetime.now()
        # Se for antes das 13h, assume janela de 10h. Depois, 14h.
        janela = "10" if agora.hour < 13 else "14"

    if data_teste:
        # Se passou uma data completa (ex: 2026-04-29_Quarta/10h)
        data_pasta = data_teste
    else:
        data_pasta = extrair_data_hoje(janela)

    # 2. Identifica e limpa pastas órfãs antes de processar
    # Tanto na origem (Auditoria) quanto na saída (Triagem)
    # Extrai o nome do dia (ex: 2026-04-28_Terca)
    dia_root = data_pasta.split(os.sep)[0]
    caminho_base_dia = os.path.join(BASE_DIR, dia_root)
    caminho_saida_dia = os.path.join(PASTA_FILTRADA, dia_root)
    
    limpar_pastas_orfas(caminho_base_dia)
    limpar_pastas_orfas(caminho_saida_dia)
    
    # Extrai o contexto para o log (ex: 10h ou manual)
    contexto = os.path.basename(data_pasta)
    print(f"\n🔍 [TRIAGEM] Iniciando processamento da janela: {contexto}")
    pasta_origem = os.path.join(BASE_DIR, data_pasta)
    pasta_saida_hoje = os.path.join(PASTA_FILTRADA, data_pasta)

    if not os.path.exists(pasta_origem):
        print(f"❌ Pasta de hoje não encontrada: {pasta_origem}")
        return

    # Limpa triagem anterior para não duplicar
    if os.path.exists(pasta_saida_hoje):
        print(f"🧹 Limpando triagem anterior em {data_pasta}...")
        shutil.rmtree(pasta_saida_hoje)

    print("\n" + "="*60)
    print("🧠 TRIAGEM DE OFERTAS v3.0 (FOCO EM PREÇO)")
    print("="*60)
    print(f"🚀 Analisando capturas de: {data_pasta}")
    
    # Define pastas locais para evitar erro de permissão no Mac
    easyocr_dir = os.path.join(BASE_DIR, ".easyocr")
    model_dir = os.path.join(easyocr_dir, "model")
    network_dir = os.path.join(easyocr_dir, "user_network")
    
    os.makedirs(model_dir, exist_ok=True)
    os.makedirs(network_dir, exist_ok=True)
    
    print("🚀 Carregando modelos de I.A. local...")
    reader = easyocr.Reader(['pt'], 
                            model_storage_directory=model_dir,
                            user_network_directory=network_dir)

    os.makedirs(pasta_saida_hoje, exist_ok=True)

    total_processado = 0
    total_aprovado = 0

    print(f"\n📂 Analisando pastas em: {data_pasta}")

    # Varre as pastas de cada supermercado/post
    for root, dirs, files in os.walk(pasta_origem):
        imagens = [f for f in files if f.lower().endswith(('.jpg', '.jpeg', '.png'))]
        
        if imagens:
            partes_caminho = root.split(os.sep)
            # Tenta pegar a loja e o post id
            try:
                loja = partes_caminho[-2]
                post_id = partes_caminho[-1]
            except IndexError:
                loja = "Geral"
                post_id = "Post"
            
            print(f"\n🔍 Loja: {loja} | Post: {post_id}")
            
            # VIA RÁPIDA: Se for do site do Assaí, aprovamos direto sem rodar o OCR
            if "assai_site" in loja.lower():
                print(f"  ⚡ [VIA RÁPIDA] Fonte confiável detectada. Copiando tudo...")
                for img in imagens:
                    total_processado += 1
                    total_aprovado += 1
                    destino_dir = os.path.join(pasta_saida_hoje, loja, post_id)
                    os.makedirs(destino_dir, exist_ok=True)
                    shutil.copy2(os.path.join(root, img), os.path.join(destino_dir, img))
                continue

            # TRIAGEM NORMAL (OCR): Para redes sociais e outras fontes
            for img in imagens:
                caminho_completo = os.path.join(root, img)
                total_processado += 1
                
                tem_preco, texto = analisar_imagem(reader, caminho_completo)
                
                if tem_preco:
                    total_aprovado += 1
                    destino_dir = os.path.join(pasta_saida_hoje, loja, post_id)
                    os.makedirs(destino_dir, exist_ok=True)
                    
                    shutil.copy2(caminho_completo, os.path.join(destino_dir, img))
                    print(f"  ✅ [APROVADO] {img} -> (Texto: {texto[:60]}...)")
                else:
                    print(f"  ⏭️ [IGNORADO] {img} (Sem indício de preço)")

    print("\n" + "="*60)
    print("🏁 TRIAGEM FINALIZADA!")
    print(f"📊 Total Analisado: {total_processado} imagens")
    print(f"⭐ Total Filtrado: {total_aprovado} imagens")
    print(f"📂 Resultados em: {pasta_saida_hoje}")
    print("="*60)

    # 4. Envio automático para a nuvem
    if total_aprovado > 0:
        print("\n🚀 [AUTO-ENVIO] Iniciando upload das ofertas filtradas...")
        try:
            import enviar_triagem
            enviar_triagem.enviar_para_nuvem()
        except ImportError:
            print("⚠️ Erro: Script 'enviar_triagem.py' não encontrado na mesma pasta.")
        except Exception as e:
            print(f"⚠️ Erro no envio automático: {e}")
    else:
        print("\n❌ Nenhuma oferta válida encontrada para enviar hoje.")

if __name__ == "__main__":
    # Permite passar a janela como argumento: python3 triagem_ofertas.py 10
    # Ou data completa para teste: python3 triagem_ofertas.py test 2026-04-29_Quarta/manual
    arg1 = sys.argv[1] if len(sys.argv) > 1 else None
    arg2 = sys.argv[2] if len(sys.argv) > 2 else None
    
    if arg1 == "test" and arg2:
        iniciar_triagem(data_teste=arg2)
    else:
        iniciar_triagem(arg1)
