# bot.py
import os
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
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.pdfgen import canvas
from config import BOT_TOKEN

# Conversation states
INPUT_TEXT = 1

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    await update.message.reply_text(
        "Welcome to Text to PDF Bot! 📄\n"
        "Send me the text you want to convert to a colorful PDF with a watermark.\n"
        "Use /cancel to stop anytime."
    )
    return INPUT_TEXT

async def receive_text(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    user_text = update.message.text
    user_id = update.message.from_user.id
    pdf_filename = f"output_{user_id}.pdf"

    # Create PDF
    try:
        generate_pdf(user_text, pdf_filename)
        # Send PDF to user
        with open(pdf_filename, 'rb') as pdf_file:
            await update.message.reply_document(
                document=pdf_file,
                filename="YourColorfulPDF.pdf",
                caption="Here's your colorful PDF with a watermark! 🎉"
            )
        # Clean up
        os.remove(pdf_filename)
    except Exception as e:
        await update.message.reply_text(f"Error creating PDF: {str(e)}")
        return INPUT_TEXT

    await update.message.reply_text(
        "PDF sent! Send more text to create another, or /cancel to stop."
    )
    return INPUT_TEXT

def generate_pdf(text, filename):
    # Create a PDF document
    doc = SimpleDocTemplate(filename, pagesize=letter)
    styles = getSampleStyleSheet()
    
    # Custom style for text
    custom_style = ParagraphStyle(
        name='Custom',
        parent=styles['Normal'],
        fontName='Helvetica',
        fontSize=12,
        leading=14,
        textColor=colors.darkblue,
        spaceAfter=12,
    )
    
    # Content for PDF
    story = []
    story.append(Paragraph(text, custom_style))
    story.append(Spacer(1, 12))

    # Build PDF with custom canvas for watermark and background
    def add_watermark_and_background(canvas, doc):
        canvas.saveState()
        # Colorful background (gradient-like)
        canvas.setFillColor(colors.lightblue)
        canvas.rect(0, 0, letter[0], letter[1], fill=1)
        # Watermark
        canvas.setFont("Helvetica-Bold", 40)
        canvas.setFillColor(colors.red, alpha=0.3)
        canvas.rotate(45)
        canvas.drawString(100, -100, "TextToPDFBot")
        canvas.restoreState()

    doc.build(story, onFirstPage=add_watermark_and_background, onLaterPages=add_watermark_and_background)

async def cancel(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    await update.message.reply_text("Operation cancelled. Use /start to begin again.")
    return ConversationHandler.END

async def error_handler(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    await update.message.reply_text("Something went wrong. Please try again or use /start.")
    print(f"Error: {context.error}")

def main() -> None:
    # Create the Application
    application = Application.builder().token(BOT_TOKEN).build()

    # Conversation handler
    conv_handler = ConversationHandler(
        entry_points=[CommandHandler("start", start)],
        states={
            INPUT_TEXT: [MessageHandler(filters.TEXT & ~filters.COMMAND, receive_text)],
        },
        fallbacks=[CommandHandler("cancel", cancel)],
    )

    # Add handlers
    application.add_handler(conv_handler)
    application.add_error_handler(error_handler)

    # Start the bot
    print("Bot is running...")
    application.run_polling(allowed_updates=Update.ALL_TYPES)

if __name__ == "__main__":
    main()
