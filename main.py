from flask import Flask, request, send_file
from docx import Document
from docx.shared import Inches, Pt
from docx.enum.text import WD_ALIGN_PARAGRAPH
import io
import base64
import matplotlib
matplotlib.use('Agg') # Backend para servidor
import matplotlib.pyplot as plt
import numpy as np

app = Flask(__name__)

@app.route('/')
def home():
    return "API Online! Envie POST para /gerar-simulado", 200

# --- FUNÇÕES DE APOIO PARA GRÁFICOS (MATPLOTLIB) ---

def desenhar_reta_numerica(dados):
    fig, ax = plt.subplots(figsize=(8, 2))
    min_val = dados.get('min_valor', dados.get('inicio', 0))
    max_val = dados.get('max_valor', dados.get('fim', 10))
    intervalo = dados.get('intervalo_principal', 1)
    marcados = dados.get('numeros_marcados', [])
    
    ax.set_xlim(min_val - intervalo, max_val + intervalo)
    ax.set_ylim(-1, 1)
    ticks = np.arange(min_val, max_val + intervalo, intervalo)
    ax.set_xticks(ticks)
    
    labels = [str(int(t)) if t in marcados else "" for t in ticks]
    ax.set_xticklabels(labels, fontsize=12, fontweight='bold')

    destaque = dados.get('ponto_destaque')
    if destaque and destaque.get('valor') is not None:
        ax.annotate(destaque.get('rotulo', 'X'), xy=(destaque['valor'], 0), xytext=(0, 15),
                    textcoords="offset points", ha='center', color=destaque.get('cor', 'red'), 
                    fontsize=14, fontweight='bold')

    ax.spines['left'].set_visible(False)
    ax.spines['right'].set_visible(False)
    ax.spines['top'].set_visible(False)
    ax.spines['bottom'].set_position('center')
    ax.yaxis.set_visible(False)
    
    img_buffer = io.BytesIO()
    plt.savefig(img_buffer, format='png', bbox_inches='tight', dpi=100)
    plt.close(fig)
    img_buffer.seek(0)
    return img_buffer

# --- FUNÇÃO PRINCIPAL DE GERAÇÃO DO DOCUMENTO ---

def criar_word_prova(dados):
    doc = Document()
    
    # Cabeçalho do Simulado
    titulo = dados.get('titulo_simulado', 'Simulado SAEB')
    heading = doc.add_heading(titulo, 0)
    heading.alignment = WD_ALIGN_PARAGRAPH.CENTER
    
    doc.add_paragraph('_' * 70)
    doc.add_paragraph('Nome: _________________________________________________ Data: ___/___/___')
    doc.add_paragraph('_' * 70)
    doc.add_paragraph()

    # Obtém a lista de itens do JSON
    itens = dados.get('itens', [])

    for i, item in enumerate(itens, 1):
        # 1. Identificação da Questão
        codigo = item.get('descritor_codigo', 'BNCC')
        nivel = item.get('nivel_dificuldade', '')
        doc.add_heading(f"QUESTÃO {i} ({codigo} - {nivel})", level=2)
        
        # 2. Enunciado (Processado estritamente dentro do loop do item atual)
        enunciado = item.get('enunciado', '[Texto da questão não disponível]')
        p = doc.add_paragraph(enunciado)
        p.paragraph_format.space_after = Pt(12)

        # 3. Imagem ou Gráfico (Sincronizado com o item atual)
        img_b64 = item.get('imagem_base64')
        dados_visuais = item.get('dados_visual_python')
        stream_para_inserir = None
        
        if img_b64:
            try:
                # Limpa o cabeçalho base64 se existir
                if "," in img_b64:
                    img_b64 = img_b64.split(",")[1]
                
                # Correção de padding
                img_b64 = img_b64.strip()
                missing_padding = len(img_b64) % 4
                if missing_padding:
                    img_b64 += '=' * (4 - missing_padding)
                
                stream_para_inserir = io.BytesIO(base64.b64decode(img_b64))
            except Exception as e:
                print(f"Erro ao processar imagem Q{i}: {e}")

        if stream_para_inserir:
            doc.add_picture(stream_para_inserir, width=Inches(3.5))
            last_p = doc.paragraphs[-1]
            last_p.alignment = WD_ALIGN_PARAGRAPH.CENTER
            doc.add_paragraph()

        # 4. Alternativas
        alts = item.get('alternativas', {})
        for letra in ['a', 'b', 'c', 'd']:
            texto_alt = alts.get(letra)
            if texto_alt:
                doc.add_paragraph(f"({letra.upper()}) {texto_alt}")
        
        doc.add_paragraph('-' * 50)

    # --- PÁGINA DE GABARITO ---
    doc.add_page_break()
    heading_gab = doc.add_heading('GABARITO COMENTADO', level=1)
    heading_gab.alignment = WD_ALIGN_PARAGRAPH.CENTER
    doc.add_paragraph()

    for i, item in enumerate(itens, 1):
        gabarito_letra = str(item.get('gabarito', '?')).upper()
        p = doc.add_paragraph()
        run = p.add_run(f"Q{i}: Gabarito {gabarito_letra}")
        run.bold = True
        
        # Suporta ambos os nomes de campos de justificativa
        dic_just = item.get('justificativa_alternativas') or item.get('justificativa_pedagogica') or {}
        
        for letra in ['a', 'b', 'c', 'd']:
            texto_just = dic_just.get(letra)
            if texto_just:
                p_just = doc.add_paragraph()
                p_just.paragraph_format.left_indent = Inches(0.3)
                run_l = p_just.add_run(f"({letra.upper()}) ")
                run_l.bold = True
                p_just.add_run(str(texto_just))
        
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
            return {"erro": "Nenhum dado recebido"}, 400
            
        arquivo = criar_word_prova(dados)
        materia = dados.get('materia', 'Geral').replace(" ", "_")
        
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
