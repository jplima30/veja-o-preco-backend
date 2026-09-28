#!/usr/bin/env python3
"""
Audita consistência entre títulos de produtos e imagens no Firebase Storage.
Usa Gemini Vision (Vertex AI) para verificar se a imagem corresponde ao produto.
Mesmo padrão de autenticação do projeto (gcloud ADC).
"""

import os, sys, json, time, requests
from google import genai
from google.genai import types

# ── Config ────────────────────────────────────────────────────────────────────
PROJECT_ID     = os.environ.get("GOOGLE_CLOUD_PROJECT", "veja-o-preco")
LOCATION       = os.environ.get("GOOGLE_CLOUD_LOCATION", "global")
MODEL          = "gemini-3.1-flash-lite"   # modelo disponível no projeto
RELATORIO_PATH = "/tmp/auditoria_imagens.json"
RELATORIO_MD   = "/tmp/auditoria_imagens.md"

# ── Lista de produtos do Firestore ────────────────────────────────────────────
# (nome, url_storage)
# Atualizada em 2026-09-23: 30 produtos incluídos/atualizados pelo CRON do dia
# (janelas 10h e 14h — inclui 5 itens automotivos Proauto que violam Food Only).
# Atualizada em 2026-09-24: +68 produtos com ofertas criadas pelos CRONs de 24/09
# (janelas 10h e 14h) — imagens subidas hoje ou nunca auditadas.
# Atualizada em 2026-09-25: +7 produtos com ofertas criadas pelos CRONs de 25/09
# (variantes "Vários Sabores/Tipos" do Mateus + 2 hotlinks VipCommerce do Econômico).
# 2 produtos do lote (bebida-nescafe-varios, composto-nutren-varios) estão SEM imagem.
PRODUTOS = [
    ("Silicone Gel Proauto 150g", "https://storage.googleapis.com/veja-o-preco.firebasestorage.app/produtos/silicone-gel-proauto-150g-un.jpg?t=1789999777"),
    ("Odorizante Proauto Líquido Várias Fragrâncias 80ml", "https://storage.googleapis.com/veja-o-preco.firebasestorage.app/produtos/odorizante-proauto-liquido-varias-fragrancias-80ml-un.jpg?t=1789999655"),
    ("Aditivo Radiador Proauto 1L", "https://storage.googleapis.com/veja-o-preco.firebasestorage.app/produtos/aditivo-radiador-proauto-1l-un.jpg?t=1789999460"),
    ("Pano de Microfibra Cockpit 4x1", "https://storage.googleapis.com/veja-o-preco.firebasestorage.app/produtos/pano-de-microfibra-cockpit-4x1-un.jpg?t=1789999684"),
    ("Água Desmineralizada Proauto 1L", "https://storage.googleapis.com/veja-o-preco.firebasestorage.app/produtos/agua-desmineralizada-proauto-1l-un.jpg?t=1789999467"),
    ("Rap 10 Integral Pullman 330g", "https://storage.googleapis.com/veja-o-preco.firebasestorage.app/produtos/rap-10-integral-pullman-330g-un.jpg?t=1789999720"),
    ("Café Santa Clara Extra Forte A Vácuo 250g", "https://storage.googleapis.com/veja-o-preco.firebasestorage.app/produtos/cafe-santa-clara-extra-forte-a-vacuo-250g-un.jpg?t=1788637794"),
    ("Sorvete De Napolitano Tradicional Nestle Pote 1.5l", "https://static.vipcommerce.com.br/img/produtos/315/v/38b33bb6-74f7-4fa0-b7c0-7a9c74445cee.jpg"),
    ("Azeite Extra Virgem Grego Mykonos 500ml", "https://storage.googleapis.com/veja-o-preco.firebasestorage.app/produtos/azeite-extra-virgem-grego-mykonos-500ml-un.jpg?t=1790010292"),
    ("Achocolatado em Pó 3 Corações Chocolatto Sachê 700g", "https://storage.googleapis.com/veja-o-preco.firebasestorage.app/produtos/achocolatado-em-po-3-coracoes-chocolatto-sache-700g-un.jpg"),
    ("Sorvete 3 Chocolates Lacta Pote 1.5l", "https://static.vipcommerce.com.br/img/produtos/315/v/e5f0ff45-f442-4c0f-bb55-9ed65ca38a52.jpg"),
    ("Biscoito Cream Cracker Estrela 350g", "https://storage.googleapis.com/veja-o-preco.firebasestorage.app/produtos/biscoito-cream-cracker-estrela-350g-un.jpg?t=1789225069"),
    ("Torrada Marilan Magic Toast Inegral 110g", "https://storage.googleapis.com/veja-o-preco.firebasestorage.app/produtos/torrada-marilan-magic-toast-inegral-110g-un.jpg?t=1790168929"),
    ("Refrigerante Guaraná Antárctica Zero 2l", "https://storage.googleapis.com/veja-o-preco.firebasestorage.app/produtos/refrigerante-guarana-antarctica-zero-2l-un.jpg?t=1788272036"),
    ("Cappuccino Santa Clara Classic Gf 26o Ml", "https://storage.googleapis.com/veja-o-preco.firebasestorage.app/produtos/cappuccino-santa-clara-classic-gf-26o-ml-un.jpg"),
    ("Coco Ralado Sococo Sweet Umido Adocado 100g", "https://storage.googleapis.com/veja-o-preco.firebasestorage.app/produtos/coco-ralado-sococo-sweet-umido-adocado-100g-un.jpg?t=1789179931"),
    ("Leite De Soja Em Pó Soy+ 300g Morango", "https://storage.googleapis.com/veja-o-preco.firebasestorage.app/produtos/leite-de-soja-em-po-soy-300g-morango-un.jpg?t=1789179923"),
    ("Refrigerante Pepsi Cola 1.5l", "https://storage.googleapis.com/veja-o-preco.firebasestorage.app/produtos/refrigerante-pepsi-cola-15l-un.jpg?t=1789179916"),
    ("Canela Em Po Br Spices 50g", "https://storage.googleapis.com/veja-o-preco.firebasestorage.app/produtos/canela-em-po-br-spices-50g-un.jpg?t=1789823509"),
    ("Tempero Para Hamburguer Heinz 80g", "https://storage.googleapis.com/veja-o-preco.firebasestorage.app/produtos/tempero-para-hamburguer-heinz-80g-un.jpg?t=1789837552"),
    ("Café Solúvel Liofilizado Tradicional 3 Corações Refil 40g", "https://storage.googleapis.com/veja-o-preco.firebasestorage.app/produtos/cafe-soluvel-liofilizado-tradicional-3-coracoes-refil-40g-un.jpg?t=1788984720"),
    ("Creme Dental Tandy Uvaventura 50g", "https://storage.googleapis.com/veja-o-preco.firebasestorage.app/produtos/creme-dental-tandy-uvaventura-50g-un.jpg?t=1789489651"),
    ("Café Em Cápsulas Três Corações Portinari Notas Frutadas C/10 Unidades 80g", "https://storage.googleapis.com/veja-o-preco.firebasestorage.app/produtos/cafe-em-capsulas-tres-coracoes-portinari-notas-frutadas-c10-unidades-80g-un.jpg?t=1788984235"),
    ("Café Em Cápsula De Café Filtrado Gourmet Tres Com 10 Cápsulas", "https://storage.googleapis.com/veja-o-preco.firebasestorage.app/produtos/cafe-em-capsula-de-cafe-filtrado-gourmet-tres-com-10-capsulas-un.jpg?t=1788984502"),
    ("Biscoito Amori Wafer Mousse De Limao", "https://storage.googleapis.com/veja-o-preco.firebasestorage.app/produtos/biscoito-amori-wafer-mousse-de-limao-un.jpg?t=1789489545"),
    ("Peixe Tambaqui", "https://storage.googleapis.com/veja-o-preco.firebasestorage.app/produtos/peixe-tambaqui-kg.jpg?t=1790168922"),
    ("Peixe Dourada", "https://storage.googleapis.com/veja-o-preco.firebasestorage.app/produtos/peixe-dourada-kg.jpg?t=1790168916"),
    ("Pão de Forma Massa e Forno", "https://storage.googleapis.com/veja-o-preco.firebasestorage.app/produtos/pao-de-forma-massa-e-forno-un.jpg?t=1790168910"),
    ("Odorizante Proauto Líquido 80ml", "https://storage.googleapis.com/veja-o-preco.firebasestorage.app/produtos/odorizante-proauto-liquido-80ml-un.jpg?t=1790168904"),
    ("Melão Pele de Sapo", "https://storage.googleapis.com/veja-o-preco.firebasestorage.app/produtos/melao-pele-de-sapo-kg.jpg?t=1790168895"),
    # ── Lote 24/09: imagens subidas pelo CRON de hoje (nunca auditadas) ──
    ("Achocolatado em Pó Nescau Act-Go 550g", "https://storage.googleapis.com/veja-o-preco.firebasestorage.app/produtos/achocolatado-em-po-nescau-actgo-550g-un.jpg?t=1790265358"),
    ("Alimento a Base de Manteiga Favorita", "https://storage.googleapis.com/veja-o-preco.firebasestorage.app/produtos/alimento-a-base-de-manteiga-favorita-un.jpg?t=1790265365"),
    ("Ave Fiesta Seara", "https://storage.googleapis.com/veja-o-preco.firebasestorage.app/produtos/ave-fiesta-seara-un.jpg?t=1790265373"),
    ("Aveia Nestlé", "https://storage.googleapis.com/veja-o-preco.firebasestorage.app/produtos/aveia-nestle-un.jpg?t=1790265379"),
    ("Bacon Suíno Seara", "https://storage.googleapis.com/veja-o-preco.firebasestorage.app/produtos/bacon-suino-seara-kg.jpg?t=1790265385"),
    ("Batata Pré-Frita Congelada", "https://storage.googleapis.com/veja-o-preco.firebasestorage.app/produtos/batata-prefrita-congelada-un.jpg?t=1790265392"),
    ("Bebida Láctea Nescafé 270ml", "https://storage.googleapis.com/veja-o-preco.firebasestorage.app/produtos/bebida-lactea-nescafe-270ml-un.jpg?t=1790265400"),
    ("Bebida Láctea Nescafé", "https://storage.googleapis.com/veja-o-preco.firebasestorage.app/produtos/bebida-lactea-nescafe-un.jpg?t=1790265406"),
    ("Bebida Vegana Vida Veg Coffee Baunilha 250ml", "https://storage.googleapis.com/veja-o-preco.firebasestorage.app/produtos/bebida-vegana-vida-veg-coffee-baunilha-250ml-un.jpg?t=1790265413"),
    ("Biscoito Choco Biscuit Nestlé 78g", "https://storage.googleapis.com/veja-o-preco.firebasestorage.app/produtos/biscoito-choco-biscuit-nestle-78g-un.jpg?t=1790269531"),
    ("Biscoito Choco Biscuit Nestlé Ao Leite 78g", "https://storage.googleapis.com/veja-o-preco.firebasestorage.app/produtos/biscoito-choco-biscuit-nestle-ao-leite-78g-un.jpg?t=1790265420"),
    ("Biscoito Choco Biscuit Nestlé", "https://storage.googleapis.com/veja-o-preco.firebasestorage.app/produtos/biscoito-choco-biscuit-nestle-un.jpg?t=1790265426"),
    ("Biscoito Cream Cracker", "https://storage.googleapis.com/veja-o-preco.firebasestorage.app/produtos/biscoito-cream-cracker-un.jpg?t=1790265433"),
    ("Café Rancheiro Extra Forte", "https://storage.googleapis.com/veja-o-preco.firebasestorage.app/produtos/cafe-rancheiro-extra-forte-un.jpg?t=1790265439"),
    ("Café Solúvel Dolca Nescafé", "https://storage.googleapis.com/veja-o-preco.firebasestorage.app/produtos/cafe-soluvel-dolca-nescafe-un.jpg?t=1790265445"),
    ("Capsula Nescafé Dolce Gusto 170g", "https://storage.googleapis.com/veja-o-preco.firebasestorage.app/produtos/capsula-nescafe-dolce-gusto-170g-un.jpg?t=1790265456"),
    ("Capsula Nescafé Dolce Gusto", "https://storage.googleapis.com/veja-o-preco.firebasestorage.app/produtos/capsula-nescafe-dolce-gusto-un.jpg?t=1790265474"),
    ("Choco Biscuit Garoto Ao Leite 78g", "https://storage.googleapis.com/veja-o-preco.firebasestorage.app/produtos/choco-biscuit-garoto-ao-leite-78g-un.jpg?t=1790265480"),
    ("Choco Biscuit Garoto", "https://storage.googleapis.com/veja-o-preco.firebasestorage.app/produtos/choco-biscuit-garoto-un.jpg?t=1790265486"),
    ("Chocolate em Barra Nestlé 80g-90g", "https://storage.googleapis.com/veja-o-preco.firebasestorage.app/produtos/chocolate-em-barra-nestle-80g90g-un.jpg?t=1790265492"),
    ("Chouriço D'paraña", "https://storage.googleapis.com/veja-o-preco.firebasestorage.app/produtos/chourico-dparaa-kg.jpg?t=1790265499"),
    ("Composto Alimentar Nutren 400g", "https://storage.googleapis.com/veja-o-preco.firebasestorage.app/produtos/composto-alimentar-nutren-400g-un.jpg?t=1790265506"),
    ("Composto Alimentar Nutren", "https://storage.googleapis.com/veja-o-preco.firebasestorage.app/produtos/composto-alimentar-nutren-un.jpg?t=1790265512"),
    ("Guaraná Antártica", "https://storage.googleapis.com/veja-o-preco.firebasestorage.app/produtos/guarana-antartica-un.jpg?t=1790265518"),
    ("Leite Condensado Nestlé", "https://storage.googleapis.com/veja-o-preco.firebasestorage.app/produtos/leite-condensado-nestle-un.jpg?t=1790265524"),
    ("Leite em Pó Molico Desnatado 280g", "https://storage.googleapis.com/veja-o-preco.firebasestorage.app/produtos/leite-em-po-molico-desnatado-280g-un.jpg?t=1790265530"),
    ("Leite em Pó Molico", "https://storage.googleapis.com/veja-o-preco.firebasestorage.app/produtos/leite-em-po-molico-un.jpg?t=1790265535"),
    ("Lombo Suíno Sulita", "https://storage.googleapis.com/veja-o-preco.firebasestorage.app/produtos/lombo-suino-sulita-kg.jpg?t=1790265542"),
    ("Nescau Nestlé Lata 200g", "https://storage.googleapis.com/veja-o-preco.firebasestorage.app/produtos/nescau-nestle-lata-200g-un.jpg?t=1790265549"),
    ("Nescau Nestlé", "https://storage.googleapis.com/veja-o-preco.firebasestorage.app/produtos/nescau-nestle-un.jpg?t=1790265556"),
    ("Ninho Forti+", "https://storage.googleapis.com/veja-o-preco.firebasestorage.app/produtos/ninho-forti-un.jpg?t=1790265564"),
    ("Ninho Forti+ Zero Lactose 380g", "https://storage.googleapis.com/veja-o-preco.firebasestorage.app/produtos/ninho-forti-zero-lactose-380g-un.jpg?t=1790265570"),
    ("Nutren Nestlé Kids 350g", "https://storage.googleapis.com/veja-o-preco.firebasestorage.app/produtos/nutren-nestle-kids-350g-un.jpg?t=1790265575"),
    ("Nutren Nestlé Kids", "https://storage.googleapis.com/veja-o-preco.firebasestorage.app/produtos/nutren-nestle-kids-un.jpg?t=1790265584"),
    ("Óleo de Milho Sinhá", "https://storage.googleapis.com/veja-o-preco.firebasestorage.app/produtos/oleo-de-milho-sinha-un.jpg?t=1790265591"),
    ("Orelha Suína Ideal", "https://storage.googleapis.com/veja-o-preco.firebasestorage.app/produtos/orelha-suina-ideal-kg.jpg?t=1790265596"),
    ("Paio Suíno Torresmo", "https://storage.googleapis.com/veja-o-preco.firebasestorage.app/produtos/paio-suino-torresmo-kg.jpg?t=1790265602"),
    ("Panceta Suína Temperada Sulita", "https://storage.googleapis.com/veja-o-preco.firebasestorage.app/produtos/panceta-suina-temperada-sulita-kg.jpg?t=1790265611"),
    ("Pé Suíno Ideal", "https://storage.googleapis.com/veja-o-preco.firebasestorage.app/produtos/pe-suino-ideal-kg.jpg?t=1790265617"),
    ("Picanha Suína Sulita", "https://storage.googleapis.com/veja-o-preco.firebasestorage.app/produtos/picanha-suina-sulita-kg.jpg?t=1790265626"),
    ("Protetor Solar Principia FPS 35", "https://storage.googleapis.com/veja-o-preco.firebasestorage.app/produtos/protetor-solar-principia-fps-35-un.jpg?t=1790265631"),
    ("Protetor Solar Principia FPS 60", "https://storage.googleapis.com/veja-o-preco.firebasestorage.app/produtos/protetor-solar-principia-fps-60-un.jpg?t=1790265637"),
    ("Protetor Solar Principia FPS 99", "https://storage.googleapis.com/veja-o-preco.firebasestorage.app/produtos/protetor-solar-principia-fps-99-un.jpg?t=1790265642"),
    ("Protetor Solar Principia", "https://storage.googleapis.com/veja-o-preco.firebasestorage.app/produtos/protetor-solar-principia-un.jpg?t=1790265649"),
    ("Sobrepaleta Suína Sulita", "https://storage.googleapis.com/veja-o-preco.firebasestorage.app/produtos/sobrepaleta-suina-sulita-kg.jpg?t=1790265658"),
    ("Tempero e Sabor Maggi", "https://storage.googleapis.com/veja-o-preco.firebasestorage.app/produtos/tempero-e-sabor-maggi-un.jpg?t=1790265664"),
    ("Toucinho Suíno Ideal", "https://storage.googleapis.com/veja-o-preco.firebasestorage.app/produtos/toucinho-suino-ideal-kg.jpg?t=1790265670"),
    ("Tucupi Artesanal Concentrado", "https://storage.googleapis.com/veja-o-preco.firebasestorage.app/produtos/tucupi-artesanal-concentrado-un.jpg?t=1790265675"),
    ("Tucupi VA Artesanal", "https://storage.googleapis.com/veja-o-preco.firebasestorage.app/produtos/tucupi-va-artesanal-un.jpg?t=1790265681"),
    # ── Lote 24/09: produtos novos do CRON sem ?t= na imagem (nunca auditados) ──
    ("Achocolatado em Pó Nescau Lata", "https://storage.googleapis.com/veja-o-preco.firebasestorage.app/produtos/achocolatado-em-po-nescau-lata-cada.jpg"),
    ("Arroz Parboilizado Sepé", "https://storage.googleapis.com/veja-o-preco.firebasestorage.app/produtos/arroz-parboilizado-sepe-un.jpg"),
    ("Bebida Láctea Nescau Prontinho 180ml", "https://storage.googleapis.com/veja-o-preco.firebasestorage.app/produtos/bebida-lactea-nescau-180ml-nescau-un.jpg"),
    ("Café Solúvel Nescafé Sachê 40g", "https://storage.googleapis.com/veja-o-preco.firebasestorage.app/produtos/cafe-soluvel-dolca-nescafe-sache-40g-un.jpg"),
    ("Café Solúvel Nescafé", "https://storage.googleapis.com/veja-o-preco.firebasestorage.app/produtos/cafe-soluvel-nescafe-un.jpg"),
    ("Chocolate em Barra Garoto 80g", "https://storage.googleapis.com/veja-o-preco.firebasestorage.app/produtos/barra-de-chocolate-garoto-ao-leite-80g-un.jpg"),
    ("Chocolate em Barra Nestlé", "https://storage.googleapis.com/veja-o-preco.firebasestorage.app/produtos/chocolate-em-barra-nestle-un.jpg"),
    ("Leite Condensado Nestlé Semidesnatado 395g", "https://storage.googleapis.com/veja-o-preco.firebasestorage.app/produtos/leite-condensado-semidesnatado-moca-nestle-tp-395g-un.jpg"),
    ("Sardinha Cabo Verde", "https://storage.googleapis.com/veja-o-preco.firebasestorage.app/produtos/sardinha-cabo-verde-un.jpg"),
    ("Tempero e Sabor Maggi Sachê 50g", "https://storage.googleapis.com/veja-o-preco.firebasestorage.app/produtos/tempero-e-sabor-maggi-50g-un.jpg"),
    # ── Lote 24/09: ofertas novas com imagem antiga nunca auditada ──
    ("AVE CHESTER PERDIGÃO CONGELADA", "https://storage.googleapis.com/veja-o-preco.firebasestorage.app/produtos/ave-chester-perdigao-congelada-kg.jpg?t=1788972040"),
    ("Aveia Nestlé Flocos ou Flocos Finos 170g", "https://storage.googleapis.com/veja-o-preco.firebasestorage.app/produtos/aveia-em-flocos-finos-ou-regulares-nestle-170g-un.jpg?t=1789493218"),
    ("Bebida Láctea Nescau", "https://storage.googleapis.com/veja-o-preco.firebasestorage.app/produtos/bebida-lactea-nescau-un.jpg?t=1788636625"),
    ("Chocolate em Barra Garoto", "https://storage.googleapis.com/veja-o-preco.firebasestorage.app/produtos/chocolate-em-barra-garoto-un.jpg?t=1788636625"),
    ("Coxas e Sobrecoxas Lar", "https://storage.googleapis.com/veja-o-preco.firebasestorage.app/produtos/coxas-e-sobrecoxas-lar-kg.jpg?t=1788556310"),
    ("LINGUIÇA CALABRESA FRIMESA A GRANEL", "https://storage.googleapis.com/veja-o-preco.firebasestorage.app/produtos/linguica-calabresa-frimesa-a-granel-kg.jpg?t=1789089807"),
    ("Linguiça Calabresa Seara", "https://storage.googleapis.com/veja-o-preco.firebasestorage.app/produtos/linguica-calabresa-seara-kg.jpg?t=1789089807"),
    ("Leite em Pó Integral Piracanjuba", "https://storage.googleapis.com/veja-o-preco.firebasestorage.app/produtos/leite-em-po-integral-piracanjuba-un.jpg?t=1789143744"),
    ("Margarina Com Sal Becel 500g", "https://storage.googleapis.com/veja-o-preco.firebasestorage.app/produtos/margarina-com-sal-becel-500g-un.jpg?t=1789489656"),
    # ── Lote 25/09: ofertas novas dos CRONs de hoje (nunca auditadas) ──
    ("Café Solúvel Nescafé Vários Tipos Sachê 40g", "https://storage.googleapis.com/veja-o-preco.firebasestorage.app/produtos/cafe-soluvel-nescafe-varios-tipos-sache-40g-un.jpg"),
    ("Capsula Nescafé Dolce Gusto Vários Tipos 170g", "https://storage.googleapis.com/veja-o-preco.firebasestorage.app/produtos/capsula-nescafe-dolce-gusto-varios-sabores-170g-un.jpg?t=1790342128"),
    ("Chocolate em Barra Garoto Vários Sabores 80g", "https://storage.googleapis.com/veja-o-preco.firebasestorage.app/produtos/chocolate-em-barra-garoto-varios-sabores-80g-un.jpg?t=1790356389"),
    ("Chocolate em Barra Nestlé Vários Sabores 80g-90g", "https://storage.googleapis.com/veja-o-preco.firebasestorage.app/produtos/chocolate-em-barra-nestle-varios-sabores-80g90g-un.jpg?t=1790342155"),
    ("Nutren Nestlé Kids Vários Tipos 350g", "https://storage.googleapis.com/veja-o-preco.firebasestorage.app/produtos/nutren-nestle-kids-varios-sabores-350g-un.jpg?t=1790356418"),
    ("Rosquinha Jasmine Cenoura Mel Light 150gr", "https://static.vipcommerce.com.br/img/produtos/315/v/51aa2944-16b9-4da4-8594-87f27236bd02.jpg"),
    ("Shampoo Bio Extratus Equilibrio 250ml", "https://static.vipcommerce.com.br/img/produtos/315/v/c2fdd2cd-84a5-415a-ad72-ee73627c4668.jpg"),
]

PROMPT = """Você é um auditor de qualidade de imagens para um aplicativo de supermercado.

Produto esperado no título: "{nome}"

Analise visualmente a imagem e responda SOMENTE em JSON:
{{
  "consistente": true,
  "confianca": "ALTA",
  "o_que_vejo": "descrição curta do produto na imagem",
  "problema": null
}}

Regras:
- consistente=false se: produto errado, marca diferente da esperada, categoria diferente, texto do rótulo contradiz o título
- consistente=true mesmo que seja foto genérica/ilustrativa do produto correto
- confianca: ALTA (certeza), MEDIA (dúvida razoável), BAIXA (imagem ruim/obscura)
- problema: null se consistente, caso contrário descreva o problema em 1 frase

Responda APENAS o JSON puro, sem markdown."""


def baixar_imagem(url: str) -> bytes | None:
    try:
        r = requests.get(url, timeout=12)
        if r.status_code == 200:
            return r.content
        print(f"   ⚠️  HTTP {r.status_code}")
        return None
    except Exception as e:
        print(f"   ❌ Falha download: {e}")
        return None


def analisar(nome: str, img_bytes: bytes, client) -> dict:
    try:
        prompt = PROMPT.format(nome=nome)
        response = client.models.generate_content(
            model=MODEL,
            contents=[
                types.Part.from_bytes(data=img_bytes, mime_type="image/jpeg"),
                prompt,
            ],
        )
        texto = response.text.strip()
        # Remove possível markdown ```json ... ```
        if "```" in texto:
            partes = texto.split("```")
            for p in partes:
                p = p.strip()
                if p.startswith("json"):
                    p = p[4:].strip()
                if p.startswith("{"):
                    texto = p
                    break
        return json.loads(texto)
    except json.JSONDecodeError as e:
        return {"consistente": None, "confianca": "ERRO", "o_que_vejo": "parse error", "problema": str(e)}
    except Exception as e:
        return {"consistente": None, "confianca": "ERRO", "o_que_vejo": "erro api", "problema": str(e)}


def main():
    print("=" * 65)
    print("🔍 AUDITORIA: TÍTULO ↔ IMAGEM  (Gemini Vision)")
    print(f"   Projeto: {PROJECT_ID}  |  {len(PRODUTOS)} produtos")
    print("=" * 65)

    # Inicializa cliente Vertex AI (usa ADC / gcloud auth)
    try:
        client = genai.Client(vertexai=True, project=PROJECT_ID, location=LOCATION)
        print("✅ Vertex AI conectado\n")
    except Exception as e:
        print(f"❌ Falha ao conectar Vertex AI: {e}")
        print("   Execute: gcloud auth application-default login")
        sys.exit(1)

    resultados   = []
    inconsistentes = []
    erros        = []

    for i, (nome, url) in enumerate(PRODUTOS, 1):
        print(f"[{i:02d}/{len(PRODUTOS)}] {nome[:52]}")

        img = baixar_imagem(url)
        if not img:
            erros.append({"nome": nome, "url": url, "problema": "Falha ao baixar"})
            print("   ⛔ Pulando\n")
            continue

        res = analisar(nome, img, client)
        res["nome"] = nome
        res["url"]  = url
        resultados.append(res)

        ok = res.get("consistente")
        emoji = "✅" if ok is True else ("⛔" if ok is None else "❌")
        print(f"   {emoji} {res.get('o_que_vejo','?')[:60]}")
        if ok is False:
            print(f"   ⚡ {res.get('problema','?')}")
            inconsistentes.append(res)
        print()

        time.sleep(1.2)   # respeita rate limit

    # ── Resumo ────────────────────────────────────────────────────────────────
    total = len(resultados)
    ok_ct = sum(1 for r in resultados if r.get("consistente") is True)
    print("\n" + "=" * 65)
    print("📊 RESULTADO DA AUDITORIA")
    print("=" * 65)
    print(f"✅ Consistentes:   {ok_ct}/{total}")
    print(f"❌ Inconsistentes: {len(inconsistentes)}/{total}")
    print(f"⛔ Erros:          {len(erros)}")

    if inconsistentes:
        print("\n🚨 PRODUTOS COM IMAGEM ERRADA:")
        print("-" * 65)
        for r in inconsistentes:
            print(f"  • {r['nome']}")
            print(f"    Vejo   : {r.get('o_que_vejo','?')}")
            print(f"    Problema: {r.get('problema','?')}")
            print()

    # ── Salvar ────────────────────────────────────────────────────────────────
    with open(RELATORIO_PATH, "w", encoding="utf-8") as f:
        json.dump({
            "total": total, "consistentes": ok_ct,
            "inconsistentes": len(inconsistentes), "erros": len(erros),
            "detalhes": resultados, "problemas": inconsistentes,
        }, f, ensure_ascii=False, indent=2)

    with open(RELATORIO_MD, "w", encoding="utf-8") as f:
        f.write("# Auditoria Título ↔ Imagem\n\n")
        f.write(f"| Métrica | Valor |\n|---|---|\n")
        f.write(f"| ✅ Consistentes | {ok_ct}/{total} |\n")
        f.write(f"| ❌ Inconsistentes | {len(inconsistentes)}/{total} |\n")
        f.write(f"| ⛔ Erros | {len(erros)} |\n\n")
        if inconsistentes:
            f.write("## 🚨 Inconsistências\n\n")
            f.write("| Produto | O que vejo | Problema |\n|---|---|---|\n")
            for r in inconsistentes:
                f.write(f"| {r['nome']} | {r.get('o_que_vejo','?')} | {r.get('problema','?')} |\n")
            f.write("\n")
        f.write("## Detalhes\n\n")
        f.write("| # | Produto | OK | Conf. | O que vejo |\n|---|---|---|---|---|\n")
        for i, r in enumerate(resultados, 1):
            e = "✅" if r.get("consistente") else "❌"
            f.write(f"| {i} | {r['nome']} | {e} | {r.get('confianca','?')} | {r.get('o_que_vejo','?')} |\n")

    print(f"\n💾 JSON : {RELATORIO_PATH}")
    print(f"📄 MD   : {RELATORIO_MD}")


if __name__ == "__main__":
    main()
