import os
import logging
import soundfile as sf
import speech_recognition as sr
from telegram import Update
from telegram.ext import ApplicationBuilder, CommandHandler, MessageHandler, filters
from apscheduler.schedulers.background import BackgroundScheduler
from datetime import datetime, timedelta
from logging.handlers import TimedRotatingFileHandler

# Создание директории для логов, если её нет
if not os.path.exists('logs'):
	os.makedirs('logs')

# Настраиваем логирование с ротацией файла каждые 24 часа
log_file = "logs/bot.log"
file_handler = TimedRotatingFileHandler(log_file, when="midnight", interval=1)
file_handler.suffix = "%Y%m%d"  # Формат суффикса для файла лога
file_handler.setLevel(logging.INFO)

# Общая настройка логгера
logging.basicConfig(
	level=logging.INFO,
	format='%(asctime)s - %(levelname)s - %(message)s',
	handlers=[
		file_handler,
		logging.StreamHandler()  # Логирование и в консоль
	]
)

# Инициализация recognizer для speech_recognition
recognizer = sr.Recognizer()

def transcribe_audio_with_google(file_path):
	try:
		# Открываем аудиофайл с помощью speech_recognition
		with sr.AudioFile(file_path) as source:
			audio = recognizer.record(source)  # Читаем весь файл
		# Распознаем с помощью Google
		text = recognizer.recognize_google(audio, language="ru-RU")
		return text
	except sr.UnknownValueError:
		logging.warning("Не удалось распознать речь.")
		return ""
	except sr.RequestError as e:
		logging.error(f"Ошибка запроса к сервису Google: {e}")
		return ""

async def handle_audio(update: Update, context):
	# Скачиваем аудиофайл из сообщения
	file = await update.message.voice.get_file()
	file_path = f"{file.file_id}.oga"
	await file.download_to_drive(file_path)

	# Логируем скачивание файла
	logging.info(f"OGA файл скачан: {file_path}")

	# Читаем файл с помощью soundfile и сохраняем как wav
	wav_path = f"{file.file_id}.wav"
	try:
		data, samplerate = sf.read(file_path)
		if data.ndim > 1:
			data = data.mean(axis=1)  # Приводим к моно
		sf.write(wav_path, data, samplerate)
		logging.info(f"WAV файл создан: {wav_path}")
	except Exception as e:
		logging.error(f"Ошибка при конвертации файла: {e}")
		return

	# Преобразуем аудио в текст с помощью Google Speech Recognition
	text = transcribe_audio_with_google(wav_path)

	# Если текст пустой, сообщаем об этом пользователю
	if text.strip():
		await update.message.reply_text(text)
	else:
		await update.message.reply_text("Не удалось распознать текст.")
		logging.info(f"Результат: {text}")

	# Удаляем временные файлы
	os.remove(file_path)
	os.remove(wav_path)
	logging.info("Временные файлы удалены")

# Удаление логов старше 24 часов
def cleanup_logs():
	now = datetime.now()
	log_dir = 'logs'
	for log_file in os.listdir(log_dir):
		log_path = os.path.join(log_dir, log_file)
		if os.path.isfile(log_path):
			creation_time = datetime.fromtimestamp(os.path.getctime(log_path))
			if now - creation_time > timedelta(hours=24):
				os.remove(log_path)
				logging.info(f"Удалён старый лог файл: {log_path}")

# Команда start
async def start(update: Update, context):
	await update.message.reply_text("Привет! Отправь мне аудиосообщение, и я его преобразую в текст.")

if __name__ == "__main__":
	# Инициализация бота
	app = ApplicationBuilder().token("Вставьте свой токен телеграм").build()      #Ваш токен телеграм бота.

	# Регистрируем обработчики
	app.add_handler(CommandHandler("start", start))
	app.add_handler(MessageHandler(filters.VOICE, handle_audio))

	# Создаем планировщик задач
	scheduler = BackgroundScheduler()
	# Настраиваем задачу на удаление логов каждые 24 часа
	scheduler.add_job(cleanup_logs, 'interval', hours=24)
	# Запускаем планировщик
	scheduler.start()

	# Запускаем бота
	app.run_polling()

	# При завершении работы бота
	scheduler.shutdown()
