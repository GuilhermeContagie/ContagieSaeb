from flask import Flask, request, send_file
from docx import Document
from docx.shared import Inches, Pt
from docx.enum.text import WD_ALIGN_PARAGRAPH
import io
import base64
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
import numpy as np

app = Flask(__name__)

@app.route('/')
def home():
    return "API Online! Envie POST para /gerar-simulado", 200

# ... (Funções de desenho: desenhar_reta_numerica, desenhar_grafico_barras, criar_tabela_word permanecem iguais) ...

def criar_word_prova(dados):
    doc = Document()
    
    # Título do Simulado
    titulo = dados.get('titulo_simulado', 'Simulado SAEB')
    heading = doc.add_heading(titulo, 0)
    heading.alignment = WD_ALIGN_PARAGRAPH.CENTER
    
    doc.add_paragraph('_' * 70)
    doc.add_paragraph('Nome: _________________________________________________ Data: ___/___/___')
    doc.add_paragraph('_' * 70)
    doc.add_paragraph()

    itens = dados.get('itens', [])

    # LOOP PRINCIPAL: Processa cada item do JSON como uma unidade única
    for i, item in enumerate(itens, 1):
        codigo = item.get('descritor_codigo', 'BNCC')
        nivel = item.get('nivel_dificuldade', 'N/A')
        
        # 1. Cabeçalho da Questão
        doc.add_heading(f"QUESTÃO {i} ({codigo} - {nivel})", level=2)
        
        # 2. Enunciado (Safeguard: se não houver texto, avisa no Word)
        enunciado = item.get('enunciado')
        if not enunciado:
            enunciado = "[AVISO: Enunciado não encontrado no sistema]"
            
        p = doc.add_paragraph(enunciado)
        p.paragraph_format.space_after = Pt(12)

        # 3. Processamento de Imagens/Gráficos (Sincronizado com o item atual)
        img_b64 = item.get('imagem_base64')
        dados_visuais = item.get('dados_visual_python')
        stream_para_inserir = None
        
        if img_b64:
            try:
                # Limpeza e correção de padding do Base64
                img_b64 = img_b64.strip().replace("data:image/png;base64,", "").replace("data:image/jpeg;base64,", "")
                missing_padding = len(img_b64) % 4
                if missing_padding: img_b64 += '=' * (4 - missing_padding)
                stream_para_inserir = io.BytesIO(base64.b64decode(img_b64))
            except Exception as e:
                doc.add_paragraph(f"(Erro ao carregar imagem da questão: {e})")

        elif dados_visuais:
            tipo = str(dados_visuais.get('tipo_grafico') or dados_visuais.get('tipo') or '').lower()
            try:
                if 'reta' in tipo or 'numerica' in tipo:
                    stream_para_inserir = desenhar_reta_numerica(dados_visuais)
                elif 'barras' in tipo or 'colunas' in tipo:
                    stream_para_inserir = desenhar_grafico_barras(dados_visuais)
                elif 'tabela' in tipo:
                    criar_tabela_word(doc, dados_visuais)
            except Exception:
                pass

        if stream_para_inserir:
            doc.add_picture(stream_para_inserir, width=Inches(3.8))
            last_p = doc.paragraphs[-1]
            last_p.alignment = WD_ALIGN_PARAGRAPH.CENTER
            doc.add_paragraph()

        # 4. Alternativas (Busca dentro do objeto 'item' atual)
        alts = item.get('alternativas', {})
        for letra in ['a', 'b', 'c', 'd']:
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
        gabarito_letra = str(item.get('gabarito', '?')).upper()
        p = doc.add_paragraph()
        run = p.add_run(f"Q{i}: Gabarito {gabarito_letra}")
        run.bold = True
        
        # Tenta buscar justificativas em múltiplos formatos possíveis
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
        if not dados: return {"erro": "Sem dados"}, 400
            
        arquivo = criar_word_prova(dados)
        materia_nome = dados.get('materia', 'Geral').replace(" ", "_")
        
        return send_file(
            arquivo,
            as_attachment=True,
            download_name=f"Simulado_{materia_nome}.docx",
            mimetype='application/vnd.openxmlformats-officedocument.wordprocessingml.document'
        )
    except Exception as e:
        return {"erro": str(e)}, 500

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000)
