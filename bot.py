import os
import logging
import re
import aiohttp
import firebase_admin
from firebase_admin import credentials, firestore
from telegram import Update, ReplyKeyboardMarkup, KeyboardButton, ReplyKeyboardRemove, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ApplicationBuilder, ContextTypes, MessageHandler, filters, CommandHandler

# --- ការកំណត់ Environment (Environment Variables) ---
BOT_TOKEN = os.getenv('BOT_TOKEN')
OCR_API_KEY = os.getenv('OCR_API_KEY')
BOT_USERNAME = 'autosenderBaggage_phone_bot'
GROUP_CHAT_ID = '-5116254772'

PORT = int(os.environ.get('PORT', '8080'))
WEBHOOK_URL = os.environ.get('WEBHOOK_URL')

logging.basicConfig(format='%(asctime)s - %(name)s - %(levelname)s - %(message)s', level=logging.INFO)

# --- ការតភ្ជាប់ទៅកាន់ Firebase ---
try:
    # ទីតាំងឯកសារ JSON ដែលអ្នកបានទាញយកពី Firebase (ត្រូវប្រាកដថាមានឯកសារនេះក្នុង Folder ជាមួយ bot.py)
    cred = credentials.Certificate("firebase-key.json")
    firebase_admin.initialize_app(cred)
    db = firestore.client()
    logging.info("✅ ភ្ជាប់ទៅកាន់ Firebase ជោគជ័យ!")
except Exception as e:
    logging.error(f"❌ មិនអាចភ្ជាប់ Firebase បានទេ៖ {e}")
    db = None

# --- មុខងារចាប់យករូបភាព និងលេខទូរស័ព្ទ ---
async def handle_photo(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("🔎 កំពុងចាប់យកលេខទូរស័ព្ទពី Cloud API...")
    
    # ទាញយករូបភាព
    photo_file = await update.message.photo[-1].get_file()
    photo_bytes = await photo_file.download_as_bytearray()

    # បោះរូបភាពទៅឱ្យ OCR.space API ស្កេន (ស៊ី RAM តិចតួចបំផុត)
    raw_text = ""
    try:
        async with aiohttp.ClientSession() as session:
            data = aiohttp.FormData()
            data.add_field('apikey', OCR_API_KEY)
            data.add_field('language', 'eng')
            data.add_field('file', photo_bytes, filename='image.jpg', content_type='image/jpeg')
            
            async with session.post('https://api.ocr.space/parse/image', data=data) as resp:
                result = await resp.json()
                
                if not result.get('IsErroredOnProcessing') and result.get('ParsedResults'):
                    for parsed_result in result['ParsedResults']:
                        raw_text += parsed_result.get('ParsedText', '')
    except Exception as e:
        logging.error(f"OCR API Error: {e}")
        await update.message.reply_text("❌ មានបញ្ហាក្នុងការភ្ជាប់ទៅកាន់ OCR API។")
        return

    # ចម្រាញ់យកតែលេខទូរស័ព្ទ
    cleaned_text = re.sub(r'\D', '', raw_text)
    phone_match = re.search(r'\d{9,10}', cleaned_text)

    if phone_match:
        detected_phone = phone_match.group()
        customer_bot_link = f"https://t.me/{BOT_USERNAME}?start={detected_phone}"
        formatted_phone = "855" + detected_phone[1:] if detected_phone.startswith('0') else detected_phone
        direct_chat_link = f"https://t.me/+{formatted_phone}"

        keyboard = [
            [InlineKeyboardButton("💬 បើក Chat ជាមួយគាត់", url=direct_chat_link)],
            [InlineKeyboardButton("🔗 ចម្លង Link ផ្ញើឱ្យគាត់", url=f"https://t.me/share/url?url={customer_bot_link}&text=សូមចុច Link នេះរួចផ្ញើទីតាំងឱ្យខ្ញុំផង")]
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)

        await context.bot.send_photo(
            chat_id=GROUP_CHAT_ID,
            photo=update.message.photo[-1].file_id,
            caption=f"📦 **មានឥវ៉ាន់ថ្មី!**\n📱 លេខទូរស័ព្ទលើប្រអប់៖ `{detected_phone}`\n\nសូមប្រើប៊ូតុងខាងក្រោមដើម្បីទាក់ទងទៅគាត់៖",
            reply_markup=reply_markup,
            parse_mode='Markdown'
        )
        await update.message.reply_text(f"✅ រកឃើញលេខ {detected_phone} និងបានបញ្ជូនទៅ Group។")
    else:
        await update.message.reply_text("❌ រកមិនឃើញលេខទូរស័ព្ទទេ ឬរូបភាពមិនច្បាស់។")

# --- មុខងារស្វាគមន៍អតិថិជន ---
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if context.args:
        expected_phone = context.args[0]
        context.user_data['expected_phone'] = expected_phone
        keyboard = [[KeyboardButton("🔐 ចុចទីនេះដើម្បីផ្ទៀងផ្ទាត់លេខទូរស័ព្ទ", request_contact=True)]]
        reply_markup = ReplyKeyboardMarkup(keyboard, one_time_keyboard=True, resize_keyboard=True)
        await update.message.reply_text("សូមចុចប៊ូតុងខាងក្រោមដើម្បីផ្ទៀងផ្ទាត់លេខទូរស័ព្ទ Telegram របស់អ្នក៖", reply_markup=reply_markup)
    else:
        await update.message.reply_text("សូមស្វាគមន៍! Bot នេះប្រើសម្រាប់តែទទួលទីតាំងដឹកឥវ៉ាន់ប៉ុណ្ណោះ។")

# --- មុខងារផ្ទៀងផ្ទាត់លេខទូរស័ព្ទ ---
async def handle_contact(update: Update, context: ContextTypes.DEFAULT_TYPE):
    contact = update.message.contact
    expected_phone = context.user_data.get('expected_phone')
    if contact and expected_phone:
        user_phone = re.sub(r'\D', '', contact.phone_number)
        formatted_expected = "855" + expected_phone[1:] if expected_phone.startswith('0') else expected_phone
        formatted_expected = re.sub(r'\D', '', formatted_expected)
        
        if user_phone == formatted_expected:
            keyboard = [[KeyboardButton("📍 ចុចទីនេះដើម្បីផ្ញើទីតាំង", request_location=True)]]
            reply_markup = ReplyKeyboardMarkup(keyboard, one_time_keyboard=True, resize_keyboard=True)
            await update.message.reply_text("✅ ការផ្ទៀងផ្ទាត់ជោគជ័យ! សូមចុចប៊ូតុងខាងក្រោមដើម្បីផ្ញើទីតាំង៖", reply_markup=reply_markup)
        else:
            await update.message.reply_text("❌ ការផ្ទៀងផ្ទាត់បរាជ័យ!", reply_markup=ReplyKeyboardRemove())

# --- មុខងារទទួលទីតាំង និងរក្សាទុកចូល Database ---
async def handle_location(update: Update, context: ContextTypes.DEFAULT_TYPE):
    location = update.message.location
    expected_phone = context.user_data.get('expected_phone', 'មិនស្គាល់លេខ')
    
    if location:
        maps_url = f"https://www.google.com/maps?q={location.latitude},{location.longitude}"
        
        # បញ្ជូនទីតាំងទៅកាន់ Group
        await context.bot.send_message(chat_id=GROUP_CHAT_ID, text=f"📍 **ទីតាំងពី៖** {expected_phone}\n🔗 {maps_url}")
        
        # --- ចាប់ផ្តើមរក្សាទុកទិន្នន័យចូល Firebase ---
        if db:
            try:
                # បង្កើត Collection ឈ្មោះ "orders" ក្នុង Firebase Database
                doc_ref = db.collection('orders').document()
                doc_ref.set({
                    'phone_number': expected_phone,
                    'telegram_user_id': update.message.from_user.id,
                    'telegram_username': update.message.from_user.username or "គ្មាន username",
                    'latitude': location.latitude,
                    'longitude': location.longitude,
                    'maps_link': maps_url,
                    'timestamp': firestore.SERVER_TIMESTAMP # កត់ត្រាម៉ោងនិងថ្ងៃខែពិតប្រាកដពី Server
                })
                logging.info(f"✅ រក្សាទុកទិន្នន័យលេខ {expected_phone} ចូល Database រួចរាល់។")
            except Exception as e:
                logging.error(f"❌ មានបញ្ហាក្នុងការរក្សាទុកទិន្នន័យ៖ {e}")
        # ---------------------------------------------
                
        await update.message.reply_text("🙏 អរគុណច្រើន! យើងបានទទួលទីតាំងនិងកត់ត្រាចូលប្រព័ន្ធរួចរាល់។", reply_markup=ReplyKeyboardRemove())

# --- ចាប់ផ្តើមដំណើរការ Bot ជា Webhook ---
if __name__ == '__main__':
    if not BOT_TOKEN:
        print("កំហុស៖ សូមដាក់ BOT_TOKEN ក្នុង Environment Variables!")
    elif not WEBHOOK_URL:
        print("កំហុស៖ សូមដាក់ WEBHOOK_URL ក្នុង Environment Variables!")
    elif not OCR_API_KEY:
        print("កំហុស៖ សូមដាក់ OCR_API_KEY ក្នុង Environment Variables!")
    else:
        app = ApplicationBuilder().token(BOT_TOKEN).build()
        
        app.add_handler(CommandHandler("start", start))
        app.add_handler(MessageHandler(filters.PHOTO, handle_photo))
        app.add_handler(MessageHandler(filters.CONTACT, handle_contact))
        app.add_handler(MessageHandler(filters.LOCATION, handle_location))
        
        print(f"🚀 Bot កំពុងដំណើរការលើ Port {PORT}...")
        
        app.run_webhook(
            listen="0.0.0.0",
            port=PORT,
            webhook_url=WEBHOOK_URL
        )
