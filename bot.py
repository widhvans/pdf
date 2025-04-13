# bot.py
import os
import re
import glob
from fonttools.ttLib import TTFont as TTFontTools
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

# Intelligent font detection
def has_devanagari_support(font_path):
    try:
        font = TTFontTools(font_path)
        # Check for Devanagari Unicode range (U+0900–U+097F)
        for table in font['cmap'].tables:
            for char_code in range(0x0900, 0x0980):
                if char_code in table.cmap:
                    return True
        return False
    except Exception:
        return False

def find_unicode_font():
    font_dirs = [
        '/usr/share/fonts/truetype/',
        '/usr/local/share/fonts/',
        '/root/.fonts/',
    ]
    font_candidates = [
        'noto/NotoSans-Regular.ttf',
        'noto/NotoSans-Bold.ttf',
        'mangal/Mangal-Regular.ttf',
        'mangal/Mangal-Bold.ttf',
        'lohit-devanagari/Lohit-Devanagari.ttf',
        'freefont/FreeSans.ttf',
        'dejavu/DejaVuSans.ttf',
    ]
    
    for font_dir in font_dirs:
        for candidate in font_candidates:
            font_path = os.path.join(font_dir, candidate)
            if os.path.exists(font_path) and has_devanagari_support(font_path):
                return font_path, os.path.basename(font_path).replace('-Regular', '').replace('.ttf', '')
    
    # Fallback to system scan
    for font_dir in font_dirs:
        ttf_files = glob.glob(os.path.join(font_dir, '**/*.ttf'), recursive=True)
        for font_path in ttf_files:
            if has_devanagari_support(font_path):
                return font_path, os.path.basename(font_path).replace('.ttf', '')
    
    return None, 'Helvetica'

# Font setup
FONT_NORMAL = 'Helvetica'
FONT_BOLD = 'Helvetica-Bold'
FONT_AVAILABLE = False

font_path, font_name = find_unicode_font()
if font_path:
    try:
        pdfmetrics.registerFont(TTFont(font_name, font_path))
        # Assume bold is same or similar
        bold_path = font_path.replace('Regular', 'Bold').replace(font_name, f"{font_name}-Bold")
        if os.path.exists(bold_path):
            pdfmetrics.registerFont(TTFont(f"{font_name}-Bold", bold_path))
            FONT_BOLD = f"{font_name}-Bold"
        else:
            FONT_BOLD = font_name  # Reuse regular if bold unavailable
        FONT_NORMAL = font_name
        FONT_AVAILABLE = True
        print(f"Loaded {font_name} from {font_path} for Hindi support.")
    except Exception as e:
        print(f"Failed to register {font_name}: {e}. Using Helvetica.")
else:
    print("No Unicode font found. Hindi may not render correctly.")

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
    'सूत्र': 'formula',
    'विशेष': 'special',
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
    
    # Dynamic font size based on text length
    total_chars = sum(len(text) for text in text_list)
    base_font_size = 16 if total_chars < 500 else 14 if total_chars < 1000 else 12
    
    normal_style = ParagraphStyle(
        name='NormalCustom',
        fontName=FONT_NORMAL,
        fontSize=base_font_size,
        leading=base_font_size + 6,
        textColor=colors.black,
        spaceAfter=12,
        alignment=0,
    )
    bold_style = ParagraphStyle(
        name='BoldCustom',
        fontName=FONT_BOLD,
        fontSize=base_font_size,
        leading=base_font_size + 6,
        textColor=colors.black,
        spaceAfter=12,
    )
    heading_style = ParagraphStyle(
        name='HeadingCustom',
        fontName=FONT_BOLD,
        fontSize=base_font_size + 4,
        leading=base_font_size + 10,
        textColor=colors.navy,
        spaceAfter=14,
        spaceBefore=14,
    )
    highlight_style = ParagraphStyle(
        name='HighlightCustom',
        fontName=FONT_BOLD,
        fontSize=base_font_size,
        leading=base_font_size + 6,
        textColor=colors.darkred,
        backColor=colors.lightyellow,
        spaceAfter=12,
        borderPadding=4,
        borderWidth=1,
        borderColor=colors.grey,
    )
    cover_style = ParagraphStyle(
        name='CoverCustom',
        fontName=FONT_BOLD,
        fontSize=30,
        leading=36,
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
                story.append(Spacer(1, 10))
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
                style = highlight_style if any(keyword.lower() in line.lower() for keyword in HINDI_KEYWORDS) or '*' in line else normal_style
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
            story.append(Spacer(1, 10))
            story.append(Paragraph("<hr width='70%' color='silver'/>", normal_style))
    
    # Watermarks and header/footer
    def add_watermarks(canvas, doc):
        canvas.saveState()
        canvas.setFillColor(colors.white)
        canvas.rect(0, 0, letter[0], letter[1], fill=1)
        
        canvas.setFont(FONT_NORMAL, 7)
        canvas.setFillColor(colors.grey, alpha=0.3)
        text_width = pdfmetrics.stringWidth(WATERMARK_TEXT, FONT_NORMAL, 7)
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
    application.run_polling(allowed_updates=Update.ALL_TYPES)

if __name__ == "__main__":
    main()
