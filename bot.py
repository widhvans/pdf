# bot.py
import os
import re
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
)
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.pdfgen import canvas
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from config import BOT_TOKEN, WATERMARK_TEXT

# Font setup with aggressive Hindi support
FONT_NORMAL = 'Helvetica'
FONT_BOLD = 'Helvetica-Bold'
FONT_AVAILABLE = False

# Try Noto Sans first
try:
    pdfmetrics.registerFont(TTFont('NotoSans', './NotoSans-Regular.ttf'))
    pdfmetrics.registerFont(TTFont('NotoSans-Bold', './NotoSans-Bold.ttf'))
    FONT_NORMAL = 'NotoSans'
    FONT_BOLD = 'NotoSans-Bold'
    FONT_AVAILABLE = True
    print("Loaded NotoSans for Hindi support.")
except Exception as e:
    print(f"NotoSans failed: {e}")
    # Try system fonts (Mangal or Lohit-Devanagari)
    try:
        pdfmetrics.registerFont(TTFont('Mangal', '/usr/share/fonts/truetype/mangal/Mangal-Regular.ttf'))
        pdfmetrics.registerFont(TTFont('Mangal-Bold', '/usr/share/fonts/truetype/mangal/Mangal-Bold.ttf'))
        FONT_NORMAL = 'Mangal'
        FONT_BOLD = 'Mangal-Bold'
        FONT_AVAILABLE = True
        print("Loaded Mangal for Hindi support.")
    except Exception as e2:
        print(f"Mangal failed: {e2}")
        try:
            pdfmetrics.registerFont(TTFont('Lohit', '/usr/share/fonts/truetype/lohit-devanagari/Lohit-Devanagari.ttf'))
            FONT_NORMAL = 'Lohit'
            FONT_BOLD = 'Lohit'  # Lohit doesn’t have bold; reuse regular
            FONT_AVAILABLE = True
            print("Loaded Lohit-Devanagari for Hindi support.")
        except Exception as e3:
            print(f"Lohit failed: {e3}. Using Helvetica (Hindi may not render).")

# Hindi study keywords
HINDI_KEYWORDS = {
    'परिभाषा': 'definition',
    'उदाहरण': 'example',
    'महत्वपूर्ण': 'important',
    'प्रश्न': 'question',
    'उत्तर': 'answer',
    'नोट्स': 'notes',
    'अध्याय': 'chapter',
    'विषय': 'topic',
    'सारांश': 'summary',
    'प्रमुख': 'key',
}

# Conversation state
INPUT_TEXT = 1

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    context.user_data['text_list'] = []
    context.user_data['pdf_filename'] = f"study_notes_{update.message.from_user.id}.pdf"
    welcome_message = (
        "Welcome to StudyBuddy PDF Bot! 📚✨\n"
        "Send your study notes in any language (e.g., Hindi, English).\n"
        "Use *text* for highlights, # for headings, - for lists, or Hindi keywords like 'परिभाषा'.\n"
        "Each message builds one PDF. Use /finish to download, or /cancel to stop."
    )
    if not FONT_AVAILABLE:
        welcome_message += "\n⚠️ Hindi text may not display correctly without proper fonts."
    await update.message.reply_text(welcome_message)
    return INPUT_TEXT

async def receive_text(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    user_text = update.message.text
    context.user_data['text_list'].append(user_text)
    
    try:
        generate_pdf(context.user_data['text_list'], context.user_data['pdf_filename'])
        await update.message.reply_text("Added to your PDF! Keep sending notes or use /finish to download.")
    except Exception as e:
        await update.message.reply_text(f"Error updating PDF: {str(e)}")
    
    return INPUT_TEXT

async def finish(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    pdf_filename = context.user_data.get('pdf_filename')
    if not context.user_data.get('text_list') or not os.path.exists(pdf_filename):
        await update.message.reply_text("No notes added yet! Send some text or use /cancel.")
        return INPUT_TEXT
    
    try:
        with open(pdf_filename, 'rb') as pdf_file:
            await update.message.reply_document(
                document=pdf_file,
                filename="YourStudyNotes.pdf",
                caption="Your stunning study notes are ready! 📝✨ Start again with /start."
            )
        os.remove(pdf_filename)
        context.user_data['text_list'] = []
    except Exception as e:
        await update.message.reply_text(f"Error sending PDF: {str(e)}")
    
    return ConversationHandler.END

async def cancel(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    pdf_filename = context.user_data.get('pdf_filename')
    if os.path.exists(pdf_filename):
        os.remove(pdf_filename)
    context.user_data['text_list'] = []
    await update.message.reply_text("Cancelled. Start fresh with /start! 🚀")
    return ConversationHandler.END

def generate_pdf(text_list, filename):
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
    
    # Styles optimized for Hindi readability
    normal_style = ParagraphStyle(
        name='NormalCustom',
        fontName=FONT_NORMAL,
        fontSize=15,
        leading=20,
        textColor=colors.black,
        spaceAfter=14,
        alignment=0,
    )
    bold_style = ParagraphStyle(
        name='BoldCustom',
        fontName=FONT_BOLD,
        fontSize=15,
        leading=20,
        textColor=colors.black,
        spaceAfter=14,
    )
    heading_style = ParagraphStyle(
        name='HeadingCustom',
        fontName=FONT_BOLD,
        fontSize=20,
        leading=24,
        textColor=colors.navy,
        spaceAfter=16,
        spaceBefore=16,
    )
    highlight_style = ParagraphStyle(
        name='HighlightCustom',
        fontName=FONT_BOLD,
        fontSize=15,
        leading=20,
        textColor=colors.darkred,
        backColor=colors.lightyellow,
        spaceAfter=14,
        borderPadding=4,
        borderWidth=1,
        borderColor=colors.grey,
    )
    cover_style = ParagraphStyle(
        name='CoverCustom',
        fontName=FONT_BOLD,
        fontSize=28,
        leading=34,
        textColor=colors.darkblue,
        alignment=1,
        spaceAfter=24,
    )
    
    # Cover page
    story = [
        Spacer(1, 2.5*inch),
        Paragraph("अध्ययन नोट्स | Study Notes", cover_style),
        Paragraph("Created with StudyBuddy Bot", normal_style),
        PageBreak()
    ]
    
    # Content
    for i, text in enumerate(text_list):
        lines = text.split('\n')
        in_list = False
        list_items = []
        
        for line in lines:
            line = line.strip()
            if not line:
                if list_items:
                    story.append(ListFlowable(
                        [ListItem(Paragraph(item, normal_style), leftIndent=10) for item in list_items],
                        bulletType='bullet',
                        start='disc',
                        leftIndent=20,
                    ))
                    list_items = []
                    in_list = False
                story.append(Spacer(1, 12))
                continue
            
            # Detect headings and Hindi keywords
            is_heading = line.startswith('#')
            clean_line = line[1:].strip() if is_heading else line
            for keyword in HINDI_KEYWORDS:
                if clean_line.startswith(keyword):
                    is_heading = True
                    clean_line = f"{keyword} ({HINDI_KEYWORDS[keyword]})"
                    break
            
            if is_heading:
                story.append(Paragraph(format_text(clean_line, normal_style, bold_style, highlight_style), heading_style))
                continue
            
            # Detect lists (including Hindi markers)
            if re.match(r'^[-*]|\d+\.|१\.|[क-ह]\.', line):
                if not in_list:
                    in_list = True
                clean_line = re.sub(r'^[-*]\s|\d+\.\s|१\.\s|[क-ह]\.\s', '', line)
                list_items.append(format_text(clean_line, normal_style, bold_style, highlight_style))
            else:
                if list_items:
                    story.append(ListFlowable(
                        [ListItem(Paragraph(item, normal_style), leftIndent=10) for item in list_items],
                        bulletType='bullet',
                        start='disc',
                        leftIndent=20,
                    ))
                    list_items = []
                    in_list = False
                formatted_line = format_text(line, normal_style, bold_style, highlight_style)
                style = highlight_style if any(keyword in line.lower() for keyword in HINDI_KEYWORDS) or '*' in line else normal_style
                story.append(Paragraph(formatted_line, style))
        
        if list_items:
            story.append(ListFlowable(
                [ListItem(Paragraph(item, normal_style), leftIndent=10) for item in list_items],
                bulletType='bullet',
                start='disc',
                leftIndent=20,
            ))
        
        # Section divider
        if i < len(text_list) - 1:
            story.append(Spacer(1, 12))
            story.append(Paragraph("<hr width='60%' color='grey'/>", normal_style))
    
    # Watermarks and header/footer
    def add_watermarks(canvas, doc):
        canvas.saveState()
        canvas.setFillColor(colors.white)
        canvas.rect(0, 0, letter[0], letter[1], fill=1)
        
        canvas.setFont(FONT_NORMAL, 8)
        canvas.setFillColor(colors.grey, alpha=0.4)
        text_width = pdfmetrics.stringWidth(WATERMARK_TEXT, FONT_NORMAL, 8)
        spacing = 15
        for x in range(-50, int(letter[0]), int(text_width + spacing)):
            canvas.drawString(x, letter[1] - 20, WATERMARK_TEXT)
            canvas.drawString(x, 10, WATERMARK_TEXT)
        canvas.rotate(90)
        for y in range(-50, int(letter[1]), int(text_width + spacing)):
            canvas.drawString(y, -letter[0] + 20, WATERMARK_TEXT)
            canvas.drawString(y, -10, WATERMARK_TEXT)
        canvas.rotate(-90)
        
        canvas.setFont(FONT_NORMAL, 36)
        canvas.setFillColor(colors.grey, alpha=0.08)
        canvas.rotate(45)
        canvas.drawCentredString(letter[0]/2, -letter[1]/2, WATERMARK_TEXT)
        
        canvas.restoreState()
    
    def add_header_footer(canvas, doc):
        add_watermarks(canvas, doc)
        canvas.saveState()
        canvas.setFont(FONT_NORMAL, 10)
        canvas.setFillColor(colors.grey)
        canvas.drawString(1*inch, 0.5*inch, f"StudyBuddy Notes | Page {doc.page}")
        canvas.drawRightString(letter[0] - 1*inch, 0.5*inch, "Created with StudyBuddy Bot")
        canvas.restoreState()
    
    doc.build(story, onFirstPage=add_header_footer, onLaterPages=add_header_footer)

def format_text(text, normal_style, bold_style, highlight_style):
    formatted = re.sub(r'\*(.*?)\*', f'<font name="{FONT_BOLD}" color="darkred">\1</font>', text)
    formatted = formatted.replace('&', '&').replace('<', '<').replace('>', '>')
    return formatted

async def error_handler(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    await update.message.reply_text("Oops, something broke! Try again or use /start. 📚")
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
    print("StudyBuddy Bot is running... 🚀")
    application.run_polling(allowed_updates=Update_ALL_TYPES)

if __name__ == "__main__":
    main()
