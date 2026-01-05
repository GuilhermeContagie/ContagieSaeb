from flask import Flask, request, send_file
from docx import Document
from docx.shared import Inches, Pt
from docx.enum.text import WD_ALIGN_PARAGRAPH
import io
import base64
import matplotlib
matplotlib.use('Agg') # Backend para servidor sem monitor
import matplotlib.pyplot as plt
import numpy as np

app = Flask(__name__)

# --- Rota de Saúde ---
@app.route('/')
def home():
    return "API Online! Envie POST para /gerar-simulado", 200

# --- FUNÇÕES DE DESENHO INTELIGENTES ---

def desenhar_reta_numerica(dados):
    fig, ax = plt.subplots(figsize=(8, 2))
    
    # Normalização de chaves (IA vs Python)
    # A IA pode mandar 'min_valor' ou 'inicio'
    min_val = dados.get('min_valor') if dados.get('min_valor') is not None else dados.get('inicio', 0)
    max_val = dados.get('max_valor') if dados.get('max_valor') is not None else dados.get('fim', 10)
    
    # Intervalo
    intervalo = dados.get('intervalo_principal') or dados.get('incremento_principal') or 1
    
    # Marcas: pode ser lista simples [10, 20] ou dicionário {"120": "X"}
    marcados = dados.get('numeros_marcados') or dados.get('marcas_texto') or []
    
    # Configura eixos
    ax.set_xlim(min_val - intervalo, max_val + intervalo)
    ax.set_ylim(-1, 1)
    
    # Limpeza visual
    ax.spines['left'].set_visible(False)
    ax.spines['right'].set_visible(False)
    ax.spines['top'].set_visible(False)
    ax.spines['bottom'].set_position('center')
    ax.yaxis.set_visible(False)
    
    # Ticks
    ticks = np.arange(min_val, max_val + intervalo, intervalo)
    ax.set_xticks(ticks)
    
    # Rótulos Inteligentes
    labels = []
    if isinstance(marcados, dict):
        # Se for dicionário (ex: {"120": "X"}), usa os valores do dict
        for t in ticks:
            # Converte t para inteiro e string para buscar na chave
            key = str(int(t))
            if key in marcados:
                labels.append(marcados[key]) # Põe o "X" ou o número
            else:
                labels.append('')
    else:
        # Se for lista (ex: [10, 20, 30])
        for t in ticks:
            if t in marcados:
                labels.append(str(int(t)))
            else:
                labels.append('')
            
    ax.set_xticklabels(labels, fontsize=12, fontweight='bold')
    
    # Setas nas pontas
    ax.plot(1, 0, ">k", transform=ax.get_yaxis_transform(), clip_on=False)
    ax.plot(0, 0, "<k", transform=ax.get_yaxis_transform(), clip_on=False)

    # Buffer
    img_buffer = io.BytesIO()
    plt.savefig(img_buffer, format='png', bbox_inches='tight', dpi=100)
    plt.close(fig)
    img_buffer.seek(0)
    return img_buffer

def desenhar_grafico_barras(dados):
    fig, ax = plt.subplots(figsize=(6, 4))
    
    categorias = dados.get('categorias') or dados.get('titulos') or []
    valores = dados.get('valores') or []
    titulo = dados.get('titulo', '')
    
    cores = ['#FF9999', '#66B2FF', '#99FF99', '#FFCC99', '#c2c2f0']
    
    if categorias and valores:
        bars = ax.bar(categorias, valores, color=cores[:len(categorias)])
        
        ax.set_title(titulo, fontsize=14)
        ax.set_ylabel('Quantidade')
        
        for bar in bars:
            height = bar.get_height()
            ax.annotate(f'{height}',
                        xy=(bar.get_x() + bar.get_width() / 2, height),
                        xytext=(0, 3),
                        textcoords="offset points",
                        ha='center', va='bottom')

    img_buffer = io.BytesIO()
    plt.savefig(img_buffer, format='png', bbox_inches='tight', dpi=100)
    plt.close(fig)
    img_buffer.seek(0)
    return img_buffer

def criar_tabela_word(doc, dados):
    colunas = dados.get('colunas', [])
    linhas = dados.get('dados', [])
    
    if not colunas or not linhas: return

    tabela = doc.add_table(rows=1, cols=len(colunas))
    tabela.style = 'Table Grid'
    
    # Cabeçalho
    hdr_cells = tabela.rows[0].cells
    for i, col_name in enumerate(colunas):
        hdr_cells[i].text = str(col_name)
        for paragraph in hdr_cells[i].paragraphs:
            for run in paragraph.runs:
                run.font.bold = True

    # Dados
    for linha in linhas:
        row_cells = tabela.add_row().cells
        for i, valor in enumerate(linha):
            row_cells[i].text = str(valor)
            
    doc.add_paragraph()

# --- FUNÇÃO PRINCIPAL GERAÇÃO WORD ---

def criar_word_prova(dados):
    doc = Document()
    
    # Título
    titulo = dados.get('titulo_simulado', 'Simulado SAEB')
    heading = doc.add_heading(titulo, 0)
    heading.alignment = WD_ALIGN_PARAGRAPH.CENTER
    
    # Cabeçalho
    doc.add_paragraph('_' * 70)
    doc.add_paragraph('Nome: _________________________________________________ Data: ___/___/___')
    doc.add_paragraph('_' * 70)
    doc.add_paragraph()

    itens = dados.get('itens', [])

    for i, item in enumerate(itens, 1):
        codigo = item.get('descritor_codigo', '')
        nivel = item.get('nivel_dificuldade', '')
        info_extra = f" ({codigo} - {nivel})" if codigo or nivel else ""
        
        doc.add_heading(f"QUESTÃO {i} {info_extra}", level=2)
        
        enunciado = item.get('enunciado', '')
        p = doc.add_paragraph(enunciado)
        p.paragraph_format.space_after = Pt(12)

        # --- LÓGICA DE DECISÃO VISUAL ---
        img_b64 = item.get('imagem_base64')
        dados_visuais = item.get('dados_visual_python')
        stream_para_inserir = None
        
        # 1. Tenta Imagem Base64 (Pollinations)
        if img_b64:
            try:
                img_b64 = img_b64.strip()
                missing_padding = len(img_b64) % 4
                if missing_padding: img_b64 += '=' * (4 - missing_padding)
                stream_para_inserir = io.BytesIO(base64.b64decode(img_b64))
            except Exception as e:
                print(f"Erro base64 Q{i}: {e}")

        # 2. Se não tem imagem, tenta Matplotlib/Tabela
        elif dados_visuais:
            # Normaliza o tipo (pega 'tipo_grafico' ou 'tipo')
            tipo = str(dados_visuais.get('tipo_grafico') or dados_visuais.get('tipo') or '').lower()
            
            try:
                if 'reta' in tipo or 'numerica' in tipo:
                    stream_para_inserir = desenhar_reta_numerica(dados_visuais)
                elif 'barras' in tipo or 'colunas' in tipo:
                    stream_para_inserir = desenhar_grafico_barras(dados_visuais)
                elif 'tabela' in tipo:
                    criar_tabela_word(doc, dados_visuais)
            except Exception as e:
                print(f"Erro matplotlib Q{i}: {e}")

        # Insere a imagem gerada (se houver)
        if stream_para_inserir:
            doc.add_picture(stream_para_inserir, width=Inches(3.5))
            doc.paragraphs[-1].alignment = WD_ALIGN_PARAGRAPH.CENTER
            doc.add_paragraph()

        # Alternativas
        alts = item.get('alternativas', {})
        for letra in ['a', 'b', 'c', 'd', 'e']:
            texto_alt = alts.get(letra)
            if texto_alt:
                doc.add_paragraph(f"({letra.upper()}) {texto_alt}")
        
        doc.add_paragraph('-' * 50)

    # --- GABARITO ---
    doc.add_page_break()
    heading_gab = doc.add_heading('GABARITO COMENTADO', level=1)
    heading_gab.alignment = WD_ALIGN_PARAGRAPH.CENTER
    doc.add_paragraph()

    for i, item in enumerate(itens, 1):
        gabarito_letra = str(item.get('gabarito', '?')).lower()
        
        p = doc.add_paragraph()
        run = p.add_run(f"Q{i}: Gabarito {gabarito_letra.upper()}")
        run.bold = True
        run.font.size = Pt(12)
        
        dic_just = item.get('justificativa_pedagogica') or item.get('justificativa_alternativas') or {}
        
        for letra in ['a', 'b', 'c', 'd', 'e']:
            texto_just = dic_just.get(letra)
            if texto_just:
                p_just = doc.add_paragraph()
                p_just.paragraph_format.left_indent = Inches(0.3)
                p_just.paragraph_format.space_after = Pt(2)
                run_l = p_just.add_run(f"({letra.upper()}) ")
                run_l.bold = True
                p_just.add_run(texto_just)
        
        doc.add_paragraph()

    file_stream = io.BytesIO()
    doc.save(file_stream)
    file_stream.seek(0)
    return file_stream

@app.route('/gerar-simulado', methods=['POST'])
def gerar_simulado():
    try:
        dados = request.json
        if not dados:
            return {"erro": "Sem dados"}, 400
            
        arquivo = criar_word_prova(dados)
        materia = dados.get('materia', 'Geral')
        
        return send_file(
            arquivo,
            as_attachment=True,
            download_name=f"Simulado_{materia}.docx",
            mimetype='application/vnd.openxmlformats-officedocument.wordprocessingml.document'
        )
    except Exception as e:
        return {"erro": str(e)}, 500

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000)
