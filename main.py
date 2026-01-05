from flask import Flask, request, send_file
from docx import Document
from docx.shared import Inches, Pt, RGBColor
from docx.enum.text import WD_ALIGN_PARAGRAPH
from docx.oxml.ns import qn
from docx.oxml import OxmlElement
import io
import base64
import matplotlib
matplotlib.use('Agg') # Importante para rodar no servidor sem monitor
import matplotlib.pyplot as plt
import numpy as np

app = Flask(__name__)

# --- Rota de Saúde ---
@app.route('/')
def home():
    return "API Online! Envie POST para /gerar-simulado", 200

# --- FUNÇÕES DE DESENHO MATEMÁTICO ---

def desenhar_reta_numerica(dados):
    fig, ax = plt.subplots(figsize=(8, 2))
    
    min_val = dados.get('min_valor', 0)
    max_val = dados.get('max_valor', 10)
    intervalo = dados.get('intervalo_principal', 1)
    marcados = dados.get('numeros_marcados', [])
    
    # Configura o eixo X
    ax.set_xlim(min_val - intervalo, max_val + intervalo)
    ax.set_ylim(-1, 1)
    
    # Remove eixos Y e bordas desnecessárias
    ax.spines['left'].set_visible(False)
    ax.spines['right'].set_visible(False)
    ax.spines['top'].set_visible(False)
    ax.spines['bottom'].set_position('center')
    ax.yaxis.set_visible(False)
    
    # Cria os ticks (tracinhos)
    ticks = np.arange(min_val, max_val + intervalo, intervalo)
    ax.set_xticks(ticks)
    
    # Formata os rótulos (labels)
    labels = []
    for t in ticks:
        if t in marcados:
            labels.append(str(int(t)))
        else:
            labels.append('') # Deixa vazio se não for para marcar
            
    ax.set_xticklabels(labels, fontsize=12, fontweight='bold')
    
    # Adiciona setas nas pontas (estilo reta infinita)
    ax.plot(max_val + intervalo, 0, ">k", transform=ax.get_yaxis_transform(), clip_on=False)
    ax.plot(min_val - intervalo, 0, "<k", transform=ax.get_yaxis_transform(), clip_on=False)

    # Salva em buffer
    img_buffer = io.BytesIO()
    plt.savefig(img_buffer, format='png', bbox_inches='tight', dpi=100)
    plt.close(fig)
    img_buffer.seek(0)
    return img_buffer

def desenhar_grafico_barras(dados):
    fig, ax = plt.subplots(figsize=(6, 4))
    
    categorias = dados.get('categorias', []) or dados.get('titulos', [])
    valores = dados.get('valores', [])
    titulo = dados.get('titulo', '')
    
    # Cores amigáveis para crianças
    cores = ['#FF9999', '#66B2FF', '#99FF99', '#FFCC99', '#c2c2f0']
    
    bars = ax.bar(categorias, valores, color=cores[:len(categorias)])
    
    ax.set_title(titulo, fontsize=14)
    ax.set_ylabel('Quantidade')
    
    # Adiciona o valor em cima da barra
    for bar in bars:
        height = bar.get_height()
        ax.annotate(f'{height}',
                    xy=(bar.get_x() + bar.get_width() / 2, height),
                    xytext=(0, 3),  # 3 points vertical offset
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
    tabela.style = 'Table Grid' # Estilo com bordas
    
    # Cabeçalho
    hdr_cells = tabela.rows[0].cells
    for i, col_name in enumerate(colunas):
        hdr_cells[i].text = str(col_name)
        # Opcional: Negrito no cabeçalho
        for paragraph in hdr_cells[i].paragraphs:
            for run in paragraph.runs:
                run.font.bold = True

    # Dados
    for linha in linhas:
        row_cells = tabela.add_row().cells
        for i, valor in enumerate(linha):
            row_cells[i].text = str(valor)
            
    doc.add_paragraph() # Espaço após tabela

# --- FUNÇÃO PRINCIPAL ---

def criar_word_prova(dados):
    doc = Document()
    
    # Título
    titulo = dados.get('titulo_simulado', 'Simulado SAEB')
    heading = doc.add_heading(titulo, 0)
    heading.alignment = WD_ALIGN_PARAGRAPH.CENTER
    
    # Cabeçalho Aluno
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

        # --- LÓGICA VISUAL INTELIGENTE ---
        # 1. Tenta Imagem Gerada (Pollinations/IA)
        img_b64 = item.get('imagem_base64')
        
        # 2. Se não tiver imagem, tenta Dados Matemáticos (Matplotlib)
        dados_visuais = item.get('dados_visual_python')
        
        stream_para_inserir = None
        
        if img_b64:
            try:
                img_b64 = img_b64.strip()
                missing_padding = len(img_b64) % 4
                if missing_padding: img_b64 += '=' * (4 - missing_padding)
                stream_para_inserir = io.BytesIO(base64.b64decode(img_b64))
            except Exception as e:
                print(f"Erro base64 Q{i}: {e}")

        elif dados_visuais:
            tipo = dados_visuais.get('tipo_grafico', '').lower()
            try:
                if 'reta' in tipo or 'numerica' in tipo:
                    stream_para_inserir = desenhar_reta_numerica(dados_visuais)
                elif 'barras' in tipo or 'colunas' in tipo:
                    stream_para_inserir = desenhar_grafico_barras(dados_visuais)
                elif 'tabela' in tipo:
                    criar_tabela_word(doc, dados_visuais) # Tabela é direto no doc, não retorna imagem
            except Exception as e:
                print(f"Erro matplotlib Q{i}: {e}")

        # Se gerou alguma imagem (IA ou Matplotlib), insere agora
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

    # --- GABARITO COMENTADO ---
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
        
        dic_justificativas = item.get('justificativa_pedagogica') or item.get('justificativa_alternativas') or {}
        
        for letra in ['a', 'b', 'c', 'd', 'e']:
            texto_just = dic_justificativas.get(letra)
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
        if not dados: return {"erro": "Sem dados"}, 400
        return send_file(
            criar_word_prova(dados),
            as_attachment=True,
            download_name=f"Simulado_{dados.get('materia','Geral')}.docx",
            mimetype='application/vnd.openxmlformats-officedocument.wordprocessingml.document'
        )
    except Exception as e:
        return {"erro": str(e)}, 500

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000)
    except Exception as e:
        return {"erro": str(e)}, 500

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000)
