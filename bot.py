# bot.py
import os
import re
import random
from telegram import Update
from telegram.ext import (
    Application,
    CommandHandler,
    MessageHandler,
    filters,
    ContextTypes,
    ConversationHandler,
)
from reportlab.lib.pagesizes import letter
from reportlab.lib import colors
from reportlab.lib.units import inch
from reportlab.platypus import (
    SimpleDocTemplate,
    Paragraph,
    Spacer,
    ListFlowable,
    ListItem,
    PageBreak,
    Table,
    TableStyle,
)
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.pdfgen import canvas
from config import BOT_TOKEN, WATERMARK_TEXT

# Hindi keywords with colors
HINDI_KEYWORDS = {
    'परिभाषा': ('definition', colors.darkgreen),
    'उदाहरण': ('example', colors.forestgreen),
    'महत्वपूर्ण': ('important', colors.crimson),
    'प्रश्न': ('question', colors.darkblue),
    'उत्तर': ('answer', colors.red),
    'नोट्स': ('notes', colors.navy),
    'अध्याय': ('chapter', colors.navy),
    'विषय': ('topic', colors.navy),
    'सारांश': ('summary', colors.purple),
    'प्रमुख': ('key', colors.red),
    'सूत्र': ('formula', colors.orange),
    'विशेष': ('special', colors.magenta),
    'अभ्यास': ('exercise', colors.blue),
}

# Motivational quotes
QUOTES = [
    "Keep pushing—you’ve got this! 💪",
    "Every note you take is a step to success! 🌟",
    "Study hard, shine bright! ✨",
    "Your future self will thank you! 🚀",
]

# Escape Unicode for Hindi
def escape_unicode(text):
    return text.encode('utf-8').decode('utf-8')

# Chunk long text
def chunk_text(text, max_chars=80):
    words = text.split()
    chunks = []
    current_chunk = []
    current_length = 0
    for word in words:
        word_length = len(word)
        if current_length + word_length + 1 > max_chars:
            chunks.append(' '.join(current_chunk))
            current_chunk = [word]
            current_length = word_length
        else:
            current_chunk.append(word)
            current_length += word_length + 1
    if current_chunk:
        chunks.append(' '.join(current_chunk))
    return chunks

# Conversation state
INPUT_TEXT = 1

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    context.user_data['text_list'] = []
    context.user_data['key_points'] = 0
    context.user_data['pdf_filename'] = f"study_notes_{update.message.from_user.id}.pdf"
    await update.message.reply_text(
        "Welcome to StudyBuddy PDF Bot! 📚🔥\n"
        "Drop your study notes (Hindi, English, whatever!).\n"
        "Use *text* for highlights, # for headings, - for lists, or keywords like 'परिभाषा'.\n"
        "Builds a killer PDF instantly. /finish to download, /cancel to reset.\n"
        "Pro tip: Try Hindi keywords for colorful flair!"
    )
    return INPUT_TEXT

async def receive_text(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    user_text = escape_unicode(update.message.text)
    context.user_data['text_list'].append((len(context.user_data['text_list']) + 1, user_text))
    
    if any(keyword.lower() in user_text.lower() for keyword in HINDI_KEYWORDS) or '*' in user_text:
        context.user_data['key_points'] += 1
    
    try:
        generate_pdf(context.user_data['text_list'], context.user_data['pdf_filename'], context.user_data['key_points'])
        await update.message.reply_text("Locked into your PDF! Keep going or /finish to snag it.")
    except Exception as e:
        await update.message.reply_text(f"PDF hiccup: {str(e)}. Try again!")
    
    return INPUT_TEXT

async def finish(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    pdf_filename = context.user_data.get('pdf_filename')
    if not context.user_data.get('text_list') or not os.path.exists(pdf_filename):
        await update.message.reply_text("Nothing to show yet! Add notes or /cancel.")
        return INPUT_TEXT
    
    try:
        with open(pdf_filename, 'rb') as pdf_file:
            await update.message.reply_document(
                document=pdf_file,
                filename="YourStudyNotes.pdf",
                caption="Your study notes are FIRE! 🔥 Start fresh with /start."
            )
        os.remove(pdf_filename)
        context.user_data['text_list'] = []
        context.user_data['key_points'] = 0
    except Exception as e:
        await update.message.reply_text(f"Error sending PDF: {str(e)}")
    
    return ConversationHandler.END

async def cancel(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    pdf_filename = context.user_data.get('pdf_filename')
    if os.path.exists(pdf_filename):
        os.remove(pdf_filename)
    context.user_data['text_list'] = []
    context.user_data['key_points'] = 0
    await update.message.reply_text("Slate cleaned! Kick off with /start! 🚀")
    return ConversationHandler.END

def generate_pdf(text_list, filename, key_points):
    doc = SimpleDocTemplate(
        filename,
        pagesize=letter,
        leftMargin=1*inch,
        rightMargin=1*inch,
        topMargin=1*inch,
        bottomMargin=1*inch,
        title="अध्ययन नोट्स",
        author="StudyBuddy Bot"
    )
    styles = getSampleStyleSheet()
    
    # Font size logic
    total_chars = sum(len(text) for _, text in text_list)
    base_font_size = 18 if total_chars < 200 else 16 if total_chars < 400 else 14
    
    normal_style = ParagraphStyle(
        name='NormalCustom',
        fontName='Helvetica',
        fontSize=base_font_size,
        leading=base_font_size + 8,
        textColor=colors.black,
        spaceAfter=12,
        alignment=0,
    )
    bold_style = ParagraphStyle(
        name='BoldCustom',
        fontName='Helvetica-Bold',
        fontSize=base_font_size,
        leading=base_font_size + 8,
        textColor=colors.black,
        spaceAfter=12,
    )
    heading_style = ParagraphStyle(
        name='HeadingCustom',
        fontName='Helvetica-Bold',
        fontSize=base_font_size + 6,
        leading=base_font_size + 12,
        textColor=colors.navy,
        spaceAfter=14,
        spaceBefore=14,
    )
    highlight_style = ParagraphStyle(
        name='HighlightCustom',
        fontName='Helvetica-Bold',
        fontSize=base_font_size,
        leading=base_font_size + 8,
        textColor=colors.darkred,
        backColor=colors.lightyellow,
        spaceAfter=12,
        borderPadding=5,
        borderWidth=1.2,
        borderColor=colors.grey,
    )
    formula_style = ParagraphStyle(
        name='FormulaCustom',
        fontName='Helvetica-Bold',
        fontSize=base_font_size,
        leading=base_font_size + 8,
        textColor=colors.darkorange,
        backColor=colors.lightgrey,
        spaceAfter=12,
        borderPadding=5,
        borderWidth=1,
        borderColor=colors.black,
        alignment=1,
    )
    cover_style = ParagraphStyle(
        name='CoverCustom',
        fontName='Helvetica-Bold',
        fontSize=36,
        leading=42,
        textColor=colors.darkblue,
        alignment=1,
        spaceAfter=30,
    )
    checklist_style = ParagraphStyle(
        name='ChecklistCustom',
        fontName='Helvetica',
        fontSize=base_font_size - 2,
        leading=base_font_size + 4,
        textColor=colors.black,
        spaceAfter=8,
    )
    
    # Cover page
    story = [
        Spacer(1, 2*inch),
        Paragraph(escape_unicode("अध्ययन नोट्स | Study Notes"), cover_style),
        Spacer(1, 0.5*inch),
        Paragraph("Created with StudyBuddy Bot", normal_style),
        Spacer(1, 0.5*inch),
        Paragraph(f"Key Points to Revise: {key_points}", normal_style),
        PageBreak()
    ]
    
    # Content
    for section_number, text in text_list:
        story.append(Paragraph(f"Section {section_number}", heading_style))
        lines = text.split('\n')
        in_list = False
        list_items = []
        
        for line in lines:
            line = escape_unicode(line.strip())
            if not line:
                if list_items:
                    formatted_items = []
                    for item in list_items:
                        chunks = chunk_text(item)
                        for chunk in chunks:
                            is_formula = 'सूत्र' in chunk.lower() or '=' in chunk
                            is_highlight = any(keyword.lower() in chunk.lower() for keyword in HINDI_KEYWORDS) or '*' in chunk
                            formatted_chunk = format_text(chunk)
                            style = formula_style if is_formula else highlight_style if is_highlight else normal_style
                            for keyword, (en, color) in HINDI_KEYWORDS.items():
                                if re.search(rf'\b{keyword}\b', chunk, re.IGNORECASE):
                                    style = ParagraphStyle(
                                        name=f'Custom_{keyword}',
                                        parent=style,
                                        textColor=color
                                    )
                                    break
                            formatted_items.append(Paragraph(formatted_chunk + (" Revise!" if is_highlight else ""), style))
                    story.append(ListFlowable(
                        [ListItem(item, leftIndent=12) for item in formatted_items],
                        bulletType='bullet',
                        start='square',
                        leftIndent=22,
                    ))
                    list_items = []
                    in_list = False
                story.append(Spacer(1, 10))
                continue
            
            # Detect headings
            is_heading = line.startswith('#')
            clean_line = line[1:].strip() if is_heading else line
            heading_match = None
            for keyword in HINDI_KEYWORDS:
                if re.match(rf'^{keyword}\b', clean_line, re.IGNORECASE):
                    is_heading = True
                    heading_match = keyword
                    clean_line = f"{keyword} ({HINDI_KEYWORDS[keyword][0]})"
                    break
            
            if is_heading:
                style = heading_style
                if heading_match:
                    style = ParagraphStyle(
                        name=f'Heading_{heading_match}',
                        parent=heading_style,
                        textColor=HINDI_KEYWORDS[heading_match][1]
                    )
                story.append(Paragraph(format_text(clean_line), style))
                continue
            
            # Detect lists
            if re.match(r'^[-*]|\d+\.|१\.|[क-ह]\.', line):
                if not in_list:
                    in_list = True
                clean_line = re.sub(r'^[-*]\s|\d+\.\s|१\.\s|[क-ह]\.\s', '', line)
                list_items.append(clean_line)
            else:
                if list_items:
                    formatted_items = []
                    for item in list_items:
                        chunks = chunk_text(item)
                        for chunk in chunks:
                            is_formula = 'सूत्र' in chunk.lower() or '=' in chunk
                            is_highlight = any(keyword.lower() in chunk.lower() for keyword in HINDI_KEYWORDS) or '*' in chunk
                            formatted_chunk = format_text(chunk)
                            style = formula_style if is_formula else highlight_style if is_highlight else normal_style
                            for keyword, (en, color) in HINDI_KEYWORDS.items():
                                if re.search(rf'\b{keyword}\b', chunk, re.IGNORECASE):
                                    style = ParagraphStyle(
                                        name=f'Custom_{keyword}',
                                        parent=style,
                                        textColor=color
                                    )
                                    break
                            formatted_items.append(Paragraph(formatted_chunk + (" Revise!" if is_highlight else ""), style))
                    story.append(ListFlowable(
                        [ListItem(item, leftIndent=12) for item in formatted_items],
                        bulletType='bullet',
                        start='square',
                        leftIndent=22,
                    ))
                    list_items = []
                    in_list = False
                
                # Render paragraph
                chunks = chunk_text(line)
                for chunk in chunks:
                    is_formula = 'सूत्र' in chunk.lower() or '=' in chunk
                    is_highlight = any(keyword.lower() in chunk.lower() for keyword in HINDI_KEYWORDS) or '*' in chunk
                    formatted_chunk = format_text(chunk)
                    style = formula_style if is_formula else highlight_style if is_highlight else normal_style
                    for keyword, (en, color) in HINDI_KEYWORDS.items():
                        if re.search(rf'\b{keyword}\b', chunk, re.IGNORECASE):
                            style = ParagraphStyle(
                                name=f'Custom_{keyword}',
                                parent=style,
                                textColor=color
                            )
                            break
                    story.append(Paragraph(formatted_chunk + (" Revise!" if is_highlight else ""), style))
        
        if list_items:
            formatted_items = []
            for item in list_items:
                chunks = chunk_text(item)
                for chunk in chunks:
                    is_formula = 'सूत्र' in chunk.lower() or '=' in chunk
                    is_highlight = any(keyword.lower() in chunk.lower() for keyword in HINDI_KEYWORDS) or '*' in chunk
                    formatted_chunk = format_text(chunk)
                    style = formula_style if is_formula else highlight_style if is_highlight else normal_style
                    for keyword, (en, color) in HINDI_KEYWORDS.items():
                        if re.search(rf'\b{keyword}\b', chunk, re.IGNORECASE):
                            style = ParagraphStyle(
                                name=f'Custom_{keyword}',
                                parent=style,
                                textColor=color
                            )
                            break
                    formatted_items.append(Paragraph(formatted_chunk + (" Revise!" if is_highlight else ""), style))
            story.append(ListFlowable(
                [ListItem(item, leftIndent=12) for item in formatted_items],
                bulletType='bullet',
                start='square',
                leftIndent=22,
            ))
    
    # Study planner
    story.append(PageBreak())
    story.append(Paragraph("Revision Checklist", heading_style))
    checklist_data = [
        ["✅ Key Point", "Revise By"],
        *[[f"Point {i+1}", "____/__/__"] for i in range(key_points)]
    ]
    checklist_table = Table(checklist_data, colWidths=[4*inch, 2*inch])
    checklist_table.setStyle(TableStyle([
        ('FONT', (0, 0), (-1, -1), 'Helvetica', base_font_size - 2),
        ('TEXTCOLOR', (0, 0), (-1, 0), colors.navy),
        ('BACKGROUND', (0, 0), (-1, 0), colors.lightgrey),
        ('GRID', (0, 0), (-1, -1), 1, colors.grey),
        ('LEFTPADDING', (0, 0), (-1, -1), 10),
    ]))
    story.append(checklist_table)
    story.append(Spacer(1, 0.5*inch))
    story.append(Paragraph("Pro Tip: Convert notes to audio for on-the-go revision! 🎧", normal_style))
    
    # Watermarks and header/footer
    def add_watermarks(canvas, doc):
        canvas.saveState()
        canvas.setFillColor(colors.white)
        canvas.rect(0, 0, letter[0], letter[1], fill=1)
        
        canvas.setFont('Helvetica', 7)
        canvas.setFillColor(colors.grey, alpha=0.3)
        text_width = canvas.stringWidth(WATERMARK_TEXT, 'Helvetica', 7)
        spacing = 15
        for x in range(-50, int(letter[0]), int(text_width + spacing)):
            canvas.drawString(x, letter[1] - 20, WATERMARK_TEXT)
            canvas.drawString(x, 10, WATERMARK_TEXT)
        canvas.rotate(90)
        for y in range(-50, int(letter[1]), int(text_width + spacing)):
            canvas.drawString(y, -letter[0] + 20, WATERMARK_TEXT)
            canvas.drawString(y, -10, WATERMARK_TEXT)
        canvas.rotate(-90)
        
        canvas.setFont('Helvetica', 34)
        canvas.setFillColor(colors.grey, alpha=0.07)
        canvas.rotate(45)
        canvas.drawCentredString(letter[0]/2, -letter[1]/2, WATERMARK_TEXT)
        
        canvas.restoreState()
    
    def add_header_footer(canvas, doc):
        add_watermarks(canvas, doc)
        canvas.saveState()
        canvas.setFont('Helvetica', 9)
        canvas.setFillColor(colors.grey)
        canvas.drawString(1*inch, 0.5*inch, f"StudyBuddy Notes | Page {doc.page}")
        canvas.drawRightString(letter[0] - 1*inch, 0.5*inch, random.choice(QUOTES))
        canvas.restoreState()
    
    doc.build(story, onFirstPage=add_header_footer, onLaterPages=add_header_footer)

def format_text(text):
    formatted = re.sub(r'\*(.*?)\*', r'<b>\1</b>', text)
    formatted = formatted.replace('&', '&').replace('<', '<').replace('>', '>')
    return formatted

async def error_handler(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    await update.message.reply_text("Whoops, hit a snag! Retry or /start fresh. 📚")
    print(f"Error: {context.error}")

def main() -> None:
    application = Application.builder().token(BOT_TOKEN).build()
    conv_handler = ConversationHandler(
        entry_points=[CommandHandler("start", start)],
        states={
            INPUT_TEXT: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, receive_text),
                CommandHandler("finish", finish),
            ],
        },
        fallbacks=[CommandHandler("cancel", cancel)],
    )
    application.add_handler(conv_handler)
    application.add_error_handler(error_handler)
    print("StudyBuddy Bot is LIVE! 🚀")
    application.run_polling(allowed_updates=Update.ALL_TYPES)

if __name__ == "__main__":
    main()
