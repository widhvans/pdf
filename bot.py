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
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from config import BOT_TOKEN, WATERMARK_TEXT

# Try to register DejaVuSans, fall back to Helvetica
FONT_NORMAL = 'Helvetica'
FONT_BOLD = 'Helvetica-Bold'
FONT_AVAILABLE = False

try:
    # Use system DejaVuSans if available
    font_path = '/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf'
    if os.path.exists(font_path):
        pdfmetrics.registerFont(TTFont('DejaVuSans', font_path))
        pdfmetrics.registerFont(TTFont('DejaVuSans-Bold', '/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf'))
        FONT_NORMAL = 'DejaVuSans'
        FONT_BOLD = 'DejaVuSans-Bold'
        FONT_AVAILABLE = True
        print("Loaded DejaVuSans for Hindi support.")
    else:
        print("DejaVuSans not found, using Helvetica with Hindi fallback.")
except Exception as e:
    print(f"Font error: {e}. Using Helvetica.")

# Hindi keywords with colors
HINDI_KEYWORDS = {
    'प्रश्न': ('question', colors.darkblue),
    'उत्तर': ('answer', colors.red),
    'परिभाषा': ('definition', colors.darkgreen),
    'उदाहरण': ('example', colors.forestgreen),
    'महत्वपूर्ण': ('important', colors.crimson),
    'नोट्स': ('notes', colors.navy),
    'अध्याय': ('chapter', colors.navy),
    'विषय': ('topic', colors.navy),
    'सारांश': ('summary', colors.purple),
    'प्रमुख': ('key', colors.red),
    'सूत्र': ('formula', colors.orange),
    'विशेष': ('special', colors.magenta),
    'अभ्यास': ('exercise', colors.blue),
}

# Motivational badges
BADGES = [
    "Brain Buster! 🧠",
    "Knowledge King! 👑",
    "Quiz Wizard! 🪄",
    "Study Star! ⭐",
]

# Parse slide structure
def parse_slide(text):
    slide = {'number': '', 'title': '', 'content': [], 'layout': '', 'visual': ''}
    lines = text.split('\n')
    current_section = None
    for line in lines:
        line = line.strip()
        if not line:
            continue
        if line.startswith('#### Slide'):
            slide['number'] = line.replace('#### ', '').strip()
        elif line.startswith('- Title:'):
            slide['title'] = line.replace('- Title:', '').strip()
        elif line.startswith('- Content:'):
            current_section = 'content'
        elif line.startswith('- Layout:'):
            current_section = 'layout'
            slide['layout'] = line.replace('- Layout:', '').strip()
        elif line.startswith('- Visual:'):
            current_section = 'visual'
            slide['visual'] = line.replace('- Visual:', '').strip()
        elif current_section == 'content' and line.startswith('  -'):
            slide['content'].append(line[4:].strip())
    return slide

# Conversation state
INPUT_TEXT = 1

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    context.user_data['text_list'] = []
    context.user_data['question_count'] = 0
    context.user_data['pdf_filename'] = f"study_notes_{update.message.from_user.id}.pdf"
    await update.message.reply_text(
        "Welcome to StudyBuddy Quiz Bot! 📚🎉\n"
        "Send your quiz slides (Hindi, English, anything!).\n"
        "Format like: #### Slide X, Title, Question, Options, Answer.\n"
        "PDF builds instantly—gorgeous and smart. /finish to download, /cancel to reset.\n"
        "Get ready for a study glow-up!"
    )
    return INPUT_TEXT

async def receive_text(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    user_text = update.message.text
    context.user_data['text_list'].append(user_text)
    if 'प्रश्न' in user_text.lower():
        context.user_data['question_count'] += 1
    
    try:
        generate_pdf(context.user_data['text_list'], context.user_data['pdf_filename'], context.user_data['question_count'])
        await update.message.reply_text("Slide added to your quiz PDF! Keep it coming or /finish to grab it.")
    except Exception as e:
        await update.message.reply_text(f"PDF glitch: {str(e)}. Try again!")
    
    return INPUT_TEXT

async def finish(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    pdf_filename = context.user_data.get('pdf_filename')
    if not context.user_data.get('text_list') or not os.path.exists(pdf_filename):
        await update.message.reply_text("No slides yet! Add some or /cancel.")
        return INPUT_TEXT
    
    try:
        with open(pdf_filename, 'rb') as pdf_file:
            await update.message.reply_document(
                document=pdf_file,
                filename="YourQuizSlides.pdf",
                caption="Your quiz slides are pure 🔥! Start again with /start."
            )
        os.remove(pdf_filename)
        context.user_data['text_list'] = []
        context.user_data['question_count'] = 0
    except Exception as e:
        await update.message.reply_text(f"Error sending PDF: {str(e)}")
    
    return ConversationHandler.END

async def cancel(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    pdf_filename = context.user_data.get('pdf_filename')
    if os.path.exists(pdf_filename):
        os.remove(pdf_filename)
    context.user_data['text_list'] = []
    context.user_data['question_count'] = 0
    await update.message.reply_text("All cleared! Hit /start to make new magic! 🚀")
    return ConversationHandler.END

def generate_pdf(text_list, filename, question_count):
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
    total_chars = sum(len(text) for text in text_list)
    base_font_size = 18 if total_chars < 200 else 16 if total_chars < 400 else 14
    
    normal_style = ParagraphStyle(
        name='NormalCustom',
        fontName=FONT_NORMAL,
        fontSize=base_font_size,
        leading=base_font_size + 8,
        textColor=colors.black,
        spaceAfter=12,
        alignment=0,
    )
    bold_style = ParagraphStyle(
        name='BoldCustom',
        fontName=FONT_BOLD,
        fontSize=base_font_size,
        leading=base_font_size + 8,
        textColor=colors.black,
        spaceAfter=12,
    )
    heading_style = ParagraphStyle(
        name='HeadingCustom',
        fontName=FONT_BOLD,
        fontSize=base_font_size + 8,
        leading=base_font_size + 14,
        textColor=colors.navy,
        spaceAfter=16,
        spaceBefore=16,
        backColor=colors.lightcyan,
        borderPadding=5,
        borderWidth=1,
        borderColor=colors.cyan,
    )
    highlight_style = ParagraphStyle(
        name='HighlightCustom',
        fontName=FONT_BOLD,
        fontSize=base_font_size,
        leading=base_font_size + 8,
        textColor=colors.darkred,
        backColor=colors.neonyellow,
        spaceAfter=12,
        borderPadding=6,
        borderWidth=1.5,
        borderColor=colors.cyan,
    )
    answer_style = ParagraphStyle(
        name='AnswerCustom',
        fontName=FONT_BOLD,
        fontSize=base_font_size + 2,
        leading=base_font_size + 10,
        textColor=colors.red,
        backColor=colors.lightyellow,
        spaceAfter=12,
        borderPadding=6,
        borderWidth=2,
        borderColor=colors.red,
        alignment=1,
    )
    visual_style = ParagraphStyle(
        name='VisualCustom',
        fontName=FONT_NORMAL,
        fontSize=base_font_size - 2,
        leading=base_font_size + 4,
        textColor=colors.grey,
        spaceAfter=10,
        alignment=0,
        leftIndent=20,
    )
    cover_style = ParagraphStyle(
        name='CoverCustom',
        fontName=FONT_BOLD,
        fontSize=38,
        leading=44,
        textColor=colors.darkblue,
        alignment=1,
        spaceAfter=32,
        backColor=colors.lightgrey,
        borderPadding=10,
        borderWidth=2,
        borderColor=colors.navy,
    )
    summary_style = ParagraphStyle(
        name='SummaryCustom',
        fontName=FONT_NORMAL,
        fontSize=base_font_size - 2,
        leading=base_font_size + 4,
        textColor=colors.black,
        spaceAfter=8,
    )
    
    # Cover page
    story = [
        Spacer(1, 1.5*inch),
        Paragraph("अध्ययन नोट्स | Quiz Slides", cover_style),
        Spacer(1, 0.5*inch),
        Paragraph("Created with StudyBuddy Bot", normal_style),
        Spacer(1, 0.5*inch),
        Paragraph(f"Questions: {question_count}", normal_style),
        PageBreak()
    ]
    
    # Content
    answers_summary = []
    for slide_text in text_list:
        slide = parse_slide(slide_text)
        slide_number = slide['number']
        badge = random.choice(BADGES)
        
        # Slide header
        story.append(Paragraph(f"{slide_number} - {badge}", heading_style))
        if slide['title']:
            title = slide['title']
            for keyword in HINDI_KEYWORDS:
                if re.search(rf'\b{keyword}\b', title, re.IGNORECASE):
                    story.append(Paragraph(
                        title,
                        ParagraphStyle(
                            name=f'Title_{keyword}',
                            parent=heading_style,
                            textColor=HINDI_KEYWORDS[keyword][1]
                        )
                    ))
                    break
            else:
                story.append(Paragraph(title, heading_style))
        
        # Content
        in_list = False
        list_items = []
        for content_line in slide['content']:
            content_line = content_line.strip()
            if not content_line:
                continue
            
            is_answer = content_line.lower().startswith('उत्तर:')
            is_question = content_line.lower().startswith('प्रश्न:')
            is_option = re.match(r'^[A-D]\)', content_line)
            
            if is_answer:
                if list_items:
                    formatted_items = []
                    for item in list_items:
                        for keyword in HINDI_KEYWORDS:
                            if re.search(rf'\b{keyword}\b', item, re.IGNORECASE):
                                formatted_items.append(Paragraph(
                                    item,
                                    ParagraphStyle(
                                        name=f'Item_{keyword}',
                                        parent=normal_style,
                                        textColor=HINDI_KEYWORDS[keyword][1]
                                    )
                                ))
                                break
                        else:
                            formatted_items.append(Paragraph(item, normal_style))
                    story.append(ListFlowable(
                        [ListItem(item, leftIndent=12) for item in formatted_items],
                        bulletType='bullet',
                        start='circle',
                        leftIndent=22,
                    ))
                    list_items = []
                    in_list = False
                
                answer_text = content_line.replace('उत्तर:', '').strip()
                answers_summary.append((slide_number, answer_text))
                story.append(Paragraph(answer_text, answer_style))
                story.append(Paragraph("Time to Answer: ~30 seconds", normal_style))
                continue
            
            if is_question or is_option:
                if list_items:
                    formatted_items = []
                    for item in list_items:
                        for keyword in HINDI_KEYWORDS:
                            if re.search(rf'\b{keyword}\b', item, re.IGNORECASE):
                                formatted_items.append(Paragraph(
                                    item,
                                    ParagraphStyle(
                                        name=f'Item_{keyword}',
                                        parent=normal_style,
                                        textColor=HINDI_KEYWORDS[keyword][1]
                                    )
                                ))
                                break
                        else:
                            formatted_items.append(Paragraph(item, normal_style))
                    story.append(ListFlowable(
                        [ListItem(item, leftIndent=12) for item in formatted_items],
                        bulletType='bullet',
                        start='circle',
                        leftIndent=22,
                    ))
                    list_items = []
                    in_list = False
                
                if is_question:
                    story.append(Paragraph(content_line, highlight_style))
                else:
                    list_items.append(content_line)
            else:
                list_items.append(content_line)
        
        if list_items:
            formatted_items = []
            for item in list_items:
                for keyword in HINDI_KEYWORDS:
                    if re.search(rf'\b{keyword}\b', item, re.IGNORECASE):
                        formatted_items.append(Paragraph(
                            item,
                            ParagraphStyle(
                                name=f'Item_{keyword}',
                                parent=normal_style,
                                textColor=HINDI_KEYWORDS[keyword][1]
                            )
                        ))
                        break
                else:
                    formatted_items.append(Paragraph(item, normal_style))
            story.append(ListFlowable(
                [ListItem(item, leftIndent=12) for item in formatted_items],
                bulletType='bullet',
                start='circle',
                leftIndent=22,
            ))
        
        # Layout and visual
        if slide['layout']:
            story.append(Paragraph(f"Layout: {slide['layout']}", normal_style))
        if slide['visual']:
            story.append(Paragraph(f"📷 Visual: {slide['visual']}", visual_style))
        
        story.append(Spacer(1, 12))
        story.append(Paragraph("<hr width='85%' color='silver'/>", normal_style))
    
    # Summary page
    if answers_summary:
        story.append(PageBreak())
        story.append(Paragraph("Quick Answer Recap", heading_style))
        summary_data = [["Slide", "Answer"]] + [[slide_num, answer] for slide_num, answer in answers_summary]
        summary_table = Table(summary_data, colWidths=[2*inch, 4*inch])
        summary_table.setStyle(TableStyle([
            ('FONT', (0, 0), (-1, -1), FONT_NORMAL, base_font_size - 2),
            ('TEXTCOLOR', (0, 0), (-1, 0), colors.navy),
            ('BACKGROUND', (0, 0), (-1, 0), colors.lightgrey),
            ('GRID', (0, 0), (-1, -1), 1, colors.grey),
            ('LEFTPADDING', (0, 0), (-1, -1), 10),
        ]))
        story.append(summary_table)
        story.append(Spacer(1, 0.5*inch))
        story.append(Paragraph("Revise these answers daily! 🎯", normal_style))
    
    # Watermarks and header/footer
    def add_watermarks(canvas, doc):
        canvas.saveState()
        canvas.setFillColor(colors.white)
        canvas.rect(0, 0, letter[0], letter[1], fill=1)
        
        canvas.setFont(FONT_NORMAL, 7)
        canvas.setFillColor(colors.grey, alpha=0.3)
        text_width = canvas.stringWidth(WATERMARK_TEXT, FONT_NORMAL, 7)
        spacing = 15
        for x in range(-50, int(letter[0]), int(text_width + spacing)):
            canvas.drawString(x, letter[1] - 20, WATERMARK_TEXT)
            canvas.drawString(x, 10, WATERMARK_TEXT)
        canvas.rotate(90)
        for y in range(-50, int(letter[1]), int(text_width + spacing)):
            canvas.drawString(y, -letter[0] + 20, WATERMARK_TEXT)
            canvas.drawString(y, -10, WATERMARK_TEXT)
        canvas.rotate(-90)
        
        canvas.setFont(FONT_NORMAL, 34)
        canvas.setFillColor(colors.grey, alpha=0.07)
        canvas.rotate(45)
        canvas.drawCentredString(letter[0]/2, -letter[1]/2, WATERMARK_TEXT)
        
        canvas.restoreState()
    
    def add_header_footer(canvas, doc):
        add_watermarks(canvas, doc)
        canvas.saveState()
        canvas.setFont(FONT_NORMAL, 9)
        canvas.setFillColor(colors.grey)
        canvas.drawString(1*inch, 0.5*inch, f"StudyBuddy Quiz | Page {doc.page}")
        canvas.drawRightString(letter[0] - 1*inch, 0.5*inch, random.choice(BADGES))
        canvas.restoreState()
    
    doc.build(story, onFirstPage=add_header_footer, onLaterPages=add_header_footer)

async def error_handler(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    await update.message.reply_text("Oops, hit a bump! Retry or /start fresh. 📚")
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
    print("StudyBuddy Quiz Bot is LIVE! 🚀")
    application.run_polling(allowed_updates=Update.ALL_TYPES)

if __name__ == "__main__":
    main()
