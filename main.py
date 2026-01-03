from flask import Flask, request, send_file
from docx import Document
from docx.shared import Inches, Pt
from docx.enum.text import WD_ALIGN_PARAGRAPH
import io
import base64
import binascii

app = Flask(__name__)

# --- Rota de Saúde ---
@app.route('/')
def home():
    return "API Online! Envie POST para /gerar-simulado", 200

def criar_word_prova(dados):
    doc = Document()
    
    # --- TÍTULO ---
    titulo = dados.get('titulo_simulado', 'Simulado SAEB')
    heading = doc.add_heading(titulo, 0)
    heading.alignment = WD_ALIGN_PARAGRAPH.CENTER
    
    # Cabeçalho
    doc.add_paragraph('_' * 70)
    doc.add_paragraph('Nome: _______________________________ Data: ___/___/___')
    doc.add_paragraph('_' * 70)
    doc.add_paragraph()

    itens = dados.get('itens', [])

    # --- QUESTÕES ---
    for i, item in enumerate(itens, 1):
        codigo = item.get('descritor_codigo', '')
        nivel = item.get('nivel_dificuldade', '')
        info_extra = f" ({codigo} - {nivel})" if codigo or nivel else ""
        
        doc.add_heading(f"QUESTÃO {i} {info_extra}", level=2)
        
        # Enunciado
        enunciado = item.get('enunciado', '')
        p = doc.add_paragraph(enunciado)
        p.paragraph_format.space_after = Pt(12)

        # Imagem
        img_b64 = item.get('imagem_base64')
        if img_b64:
            try:
                img_b64 = img_b64.strip()
                missing_padding = len(img_b64) % 4
                if missing_padding:
                    img_b64 += '=' * (4 - missing_padding)

                image_data = base64.b64decode(img_b64)
                image_stream = io.BytesIO(image_data)
                
                doc.add_picture(image_stream, width=Inches(3.5))
                doc.paragraphs[-1].alignment = WD_ALIGN_PARAGRAPH.CENTER
                doc.add_paragraph() 
            except Exception as e:
                print(f"Erro imagem Q{i}: {e}")

        # Alternativas
        alts = item.get('alternativas', {})
        for letra in ['a', 'b', 'c', 'd', 'e']:
            texto_alt = alts.get(letra)
            if texto_alt:
                doc.add_paragraph(f"({letra.upper()}) {texto_alt}")
        
        doc.add_paragraph('-' * 50)

    # --- GABARITO COMENTADO (ATUALIZADO) ---
    doc.add_page_break()
    heading_gab = doc.add_heading('GABARITO COMENTADO', level=1)
    heading_gab.alignment = WD_ALIGN_PARAGRAPH.CENTER
    doc.add_paragraph()

    for i, item in enumerate(itens, 1):
        gabarito_letra = str(item.get('gabarito', '?')).lower()
        
        # Título da questão no gabarito
        p = doc.add_paragraph()
        run = p.add_run(f"Q{i}: Gabarito {gabarito_letra.upper()}")
        run.bold = True
        run.font.size = Pt(12)
        
        # Busca dicionário de justificativas
        dic_justificativas = item.get('justificativa_pedagogica') or item.get('justificativa_alternativas') or {}
        
        # ITERAÇÃO: Lista todas as alternativas (A, B, C, D, E)
        for letra in ['a', 'b', 'c', 'd', 'e']:
            texto_just = dic_justificativas.get(letra)
            if texto_just:
                # Cria parágrafo indentado para cada justificativa
                p_just = doc.add_paragraph()
                p_just.paragraph_format.left_indent = Inches(0.3)
                p_just.paragraph_format.space_after = Pt(2) # Espaço menor entre elas
                
                # Letra em negrito: "(A) "
                run_l = p_just.add_run(f"({letra.upper()}) ")
                run_l.bold = True
                
                # Texto da explicação
                p_just.add_run(texto_just)
                
        doc.add_paragraph() # Espaço extra entre uma questão e outra

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
