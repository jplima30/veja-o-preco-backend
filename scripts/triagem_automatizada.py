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
PASTA_FILTRADA = os.path.join(BASE_DIR, "TRIAGEM_AUTOMATIZADA")
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
    hoje_str = agora.strftime("%Y-%m-%d") # Proteção para não apagar o dia de hoje
    
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
                    if hoje_str in item:
                        continue
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
                        if hoje_str in item:
                            continue
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
TAMANHO_MINIMO_FONTE = 0.04  # Texto deve ter pelo menos 4% da altura da imagem (Padrão sugerido)
CONFIANCA_MINIMA = 0.2      # Confiança mínima do OCR (Baixada de 0.3 para 0.2)

# Padrões para PREÇOS (Aceita com vírgula, ponto ou números isolados se houver contexto)
PADRAO_PRECO_STRICT = r"(\d+[\.,]\d{1,2})"
PADRAO_PRECO_LOOSE = r"(\d+)" # Para capturar números grandes que o OCR separou dos centavos 
# Padrões para DATAS e VALIDADE (ex: 10/10 ou VALIDO ATE)
PADRAO_VALIDADE = r"(\d{2}/\d{2})"
PALAVRAS_CHAVE_URGENCIA = [
    "OFERTA", "PROMO", "DESCONTO", "DESCONT", "PRECO", "VALOR", "APENAS",
    "LEVE", "PAGUE", "CADA", "UNIDADE", "SO HOJE", "R$", "RS",
    "VALIDO ATE", "VALIDADE", "PERIODO", "ECONOMIA", "POR", "DE:",
    "OFF", "LITRO", "GRAMAS", "ML", "KG", "HORTIFRUTI", "ACOUGUE", 
    "AÇOUGUE", "PADARIA", "MERCEARIA", "LIMPEZA", "HIGIENE", "BEBIDAS", "ALIMENTOS"
]

# Categorias que bloqueiam a página INTEIRA (Seções que não queremos)
PALAVRAS_CHAVE_BLOQUEIO_SECAO = [
    "BAZAR", "ELETRO", "PNEU", "VESTUARIO", "CAMISETA", "BERMUDA", 
    "CALCA", "MEIA", "MOTO", "CARRO", "CELULAR", "SMARTPHONE", "TELEVISOR", "SMART TV", 
    "LAVADORA", "GELADEIRA", "NOTEBOOK", "TABLET", "MODA", "FASHION", 
    "CALCADO", "CALÇADO", "CHUTEIRA", "RASTEIRA", "TAMANCO", "BOTINA",
    "COLEÇÃO", "COLECAO", "VERÃO", "VERAO", "OUTONO", "INVERNO", "LOOK", "ESTILO"
]

# Categorias de produtos que queremos evitar, mas que podem estar "contaminando" uma página boa
PALAVRAS_CHAVE_BLOQUEIO_PRODUTO = [
    "CERVEJA", "WHISKY", "WHISKEY", "VODKA", "VODCA", "GIN", "VINHO", 
    "CHOPP", "CACHAÇA", "LICOR", "TEQUILA", "RUM", "ICE", "SKOL", 
    "BRAHMA", "HEINEKEN", "BUDWEISER", "SPATEN", "AMSTEL", "CORONA",
    "STELLA", "ANTARCTICA", "ITAIPAVA", "SCHIN", "KAISER", "BAVARIA",
    "CAMPARI", "ABSOLUT", "SMIRNOFF", "CHANDON", "ESPUMANTE", "CHAMPAGNE",
    "ROUPA", "BALDE", "PANELA", "FRIGIDEIRA", "FOGAO", "FOGÃO", "VENTILADOR",
    "LAMPADA", "LÂMPADA", "PILHA", "BATERIA", "BICICLETA", "CHURRASQUEIRA",
    "MESA", "CADEIRA", "ARMARIO", "GUARDA-ROUPA", "COLCHAO", "BRINQUEDO", 
    "BONECA", "CARRINHO", "JOGO", "ASPIRADOR", "LIQUIDIFICADOR", "BATEDEIRA", 
    "AIR FRYER", "MICROONDAS", "FERRO DE PASSAR", "SANDUICHEIRA", "GRILL", 
    "SMARTWATCH", "FONE", "CARREGADOR", "CAIXA DE SOM", "FURADEIRA", 
    "PARAFUSADEIRA", "MICRO-ONDAS", "SECADOR", "PRANCHA", "SANDALIA", 
    "CHINELO", "TENIS", "SAPATO", "MOCHILA", "BOLSA", "VARAL", "MOP", 
    "VASSOURA", "ESCADA"
]

FONTES_CONFIAVEIS = ["assai_site", "mateus_site"]

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
    if "test" in str(caminho_dia).lower() or os.path.isfile(caminho_dia):
        return
        
    pastas_protegidas = ["10h", "14h", "manual", "TRIAGEM_AUTOMATIZADA"]
    pasta_manual = os.path.join(caminho_dia, "manual")
    os.makedirs(pasta_manual, exist_ok=True)
    
    for item in os.listdir(caminho_dia):
        item_path = os.path.join(caminho_dia, item)
        # Se for um diretório e não for uma das pastas de janela protegidas
        if os.path.isdir(item_path) and item not in pastas_protegidas:
            # Se o item for TRIAGEM_AUTOMATIZADA (que pode estar no root do BASE_DIR, mas não dentro do dia)
            # mas aqui estamos dentro de caminho_dia, então TRIAGEM_AUTOMATIZADA não deveria estar aqui.
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
        secao_bloqueada = None
        produto_bloqueado = None
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
            
            # 1b. Busca por PREÇO "Solto" (Para números sem vírgula, exigimos pelo menos 2 dígitos OU R$)
            elif re.search(PADRAO_PRECO_LOOSE, text_upper):
                # Se tiver barra, é data. Ignoramos como preço.
                if "/" in text_upper:
                    continue

                # Extrai apenas os números para contar os dígitos
                digitos = re.sub(r"\D", "", text_upper)
                tem_minimo_digitos = len(digitos) >= 2
                
                # Filtro de pureza: Se tiver mais letras que números e não tiver R$, é ruído (ex: "48uoRas")
                letras = re.sub(r"[^A-Z]", "", text_upper)
                if len(letras) > len(digitos) and "R$" not in text_upper and "RS" not in text_upper:
                    continue

                # Só aprovamos números sem vírgula se tiverem 2+ dígitos OU o símbolo R$
                if (tem_minimo_digitos or "R$" in text_upper or "RS" in text_upper):
                    if proporcao >= TAMANHO_MINIMO_FONTE or "R$" in text_upper or "RS" in text_upper:
                        # Filtra números gigantescos que não são preços (ex: IDs longos)
                        if len(digitos) <= 4:
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
            
            # 3. Busca por categorias bloqueadas
            # 3a. Bloqueio de SEÇÃO (Fatal para qualquer fonte)
            for b in PALAVRAS_CHAVE_BLOQUEIO_SECAO:
                if b in text_upper:
                    secao_bloqueada = b
                    break
            
            # 3b. Bloqueio de PRODUTO (Pode ser flexível se houver outras coisas na página)
            for p in PALAVRAS_CHAVE_BLOQUEIO_PRODUTO:
                if p in text_upper:
                    produto_bloqueado = p
                    break
            
            if re.search(PADRAO_VALIDADE, text_upper):
                achou_urgencia_ou_data = True
                texto_extraido.append(text)

        # DECISÃO FINAL: 
        # 1. Se for uma seção proibida (Bazar/Eletro), bloqueia sempre.
        if secao_bloqueada:
            return False, f"BLOQUEIO_SECAO: {secao_bloqueada}"
        
        # 2. Se for um produto proibido (Álcool), bloqueia...
        if produto_bloqueado:
            # ...A MENOS que seja uma página densa com outros preços detectados.
            if len(texto_extraido) > 3:
                return True, "Aprovado (Misto) | " + " | ".join(texto_extraido)
            else:
                return False, f"BLOQUEIO_PRODUTO: {produto_bloqueado}"
        
        # 3. Se achou preço, aprovado.
        if achou_preco:
            return True, " | ".join(texto_extraido)
        
        return False, ""
    except Exception as e:
        print(f"      ⚠️ Erro ao analisar {os.path.basename(caminho_imagem)}: {e}")
        return False, ""

def iniciar_triagem(janela=None, data_teste=None):
    if not OCR_DISPONIVEL:
        print("❌ EasyOCR não encontrado. Instale com: pip install easyocr")
        return

    # O gatilho da faxina foi movido para o final do processo

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

    # Identifica o "Nível da Janela" (ex: 2026-05-02_Sabado/manual)
    # Isso é usado para manter a estrutura de saída consistente mesmo em testes profundos
    partes_pasta = data_pasta.split(os.sep)
    if len(partes_pasta) >= 2:
        pasta_dia_janela = os.path.join(partes_pasta[0], partes_pasta[1])
    else:
        pasta_dia_janela = data_pasta

    # Extrai o contexto para o log (ex: 10h ou manual)
    contexto = os.path.basename(data_pasta)
    print(f"\n🔍 [TRIAGEM AUTOMATIZADA] Iniciando processamento da janela: {contexto}")
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
    print("🧠 TRIAGEM AUTOMATIZADA v3.0 (FOCO EM PREÇO)")
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
            # Calcula o caminho relativo a partir do Nível da Janela (ex: manual)
            # para manter a estrutura idêntica na saída sem aninhamentos extras.
            caminho_root_bruto = os.path.join(BASE_DIR, pasta_dia_janela)
            rel_path = os.path.relpath(root, caminho_root_bruto)
            
            # Tenta pegar a loja e o post id para o log
            partes_rel = rel_path.split(os.sep)
            try:
                # Se rel_path for '.', estamos na raiz da janela
                if rel_path == ".":
                    loja = "Geral"
                    post_id = "Raiz"
                else:
                    loja = partes_rel[0]
                    post_id = partes_rel[-1] if len(partes_rel) > 1 else "Post"
            except IndexError:
                loja = "Geral"
                post_id = "Post"
            
            print(f"\n🔍 Local: {rel_path} | Loja: {loja} | Post: {post_id}")
            
            # TRIAGEM ESPECIAL (Fontes Confiáveis): Aceitamos tudo, menos o que for explicitamente bloqueado
            es_fonte_confiavel = any(f in loja.lower() for f in FONTES_CONFIAVEIS)

            for img in imagens:
                caminho_completo = os.path.join(root, img)
                total_processado += 1
                
                tem_preco, texto = analisar_imagem(reader, caminho_completo)
                
                # Lógica para SITES (Mateus/Assaí):
                # Sites são mais organizados, mas o OCR pode falhar no preço.
                # Aceitamos se (Tem Preço) OU (Não é Bazar).
                aprovado = tem_preco
                if es_fonte_confiavel:
                    # Se detectou bloqueio de seção (Sandália, etc), ignora SEMPRE.
                    if "BLOQUEIO_SECAO" in (texto or ""):
                        aprovado = False
                    else:
                        # Se não é bazar, e não achou preço, ainda damos uma chance se o OCR achou palavras de urgência
                        # ou se o texto extraído é denso (indicando uma página de produtos).
                        achou_urgencia = any(k in (texto or "").upper() for k in PALAVRAS_CHAVE_URGENCIA)
                        if not tem_preco and achou_urgencia:
                            aprovado = True
                            texto = f"Aprovado (Urgência detectada em Site)"
                        elif not tem_preco:
                            # Se não achou NADA (nem preço, nem urgência), ignoramos para evitar lixo de bazar sem texto.
                            aprovado = False
                            texto = "Ignorado (Site sem indícios de ofertas)"

                if aprovado:
                    total_aprovado += 1
                    # O destino agora é calculado a partir da pasta base de triagem + caminho relativo
                    destino_dir = os.path.join(PASTA_FILTRADA, pasta_dia_janela, rel_path)
                    os.makedirs(destino_dir, exist_ok=True)
                    
                    shutil.copy2(caminho_completo, os.path.join(destino_dir, img))
                    info_texto = f" -> (Texto: {texto[:60]}...)" if texto else ""
                    print(f"  ✅ [APROVADO] {img}{info_texto}")
                else:
                    motivo = f" ({texto})" if texto else " (Sem indício de preço)"
                    print(f"  ⏭️ [IGNORADO] {img}{motivo}")

    print("\n" + "="*60)
    print("🏁 TRIAGEM AUTOMATIZADA FINALIZADA!")
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
        except ImportError as e:
            print(f"⚠️ Erro ao carregar 'enviar_triagem.py': {e}")
            print("💡 Dica: Certifique-se de estar usando o venv correto (venv_triagem).")
        except Exception as e:
            print(f"⚠️ Erro no envio automático: {e}")
    else:
        print("\n❌ Nenhuma oferta válida encontrada para enviar hoje.")

    # 4. Realiza faxina de sábado se necessário (Movido para o final)
    realizar_faxina_semanal()

if __name__ == "__main__":
    # Permite passar a janela como argumento: python3 triagem_automatizada.py 10
    # Ou data completa para teste: python3 triagem_automatizada.py test 2026-04-29_Quarta/manual
    arg1 = sys.argv[1] if len(sys.argv) > 1 else None
    arg2 = sys.argv[2] if len(sys.argv) > 2 else None
    
    if arg1 == "test" and arg2:
        iniciar_triagem(data_teste=arg2)
    else:
        iniciar_triagem(arg1)
