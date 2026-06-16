import os
import asyncio
from aiogram import Bot, Dispatcher, types, F
from aiogram.filters import Command
from ultralytics import YOLO

# 1. Настройка токена и инициализация бота
API_TOKEN = '8973144207:AAHwDI2q0r04ESAyVGTFUtn11ZeIjmKMDYs'
SAFETY_OFFICER_ID = 509182730
bot = Bot(token=API_TOKEN)
dp = Dispatcher()

# 2. Загрузка твоей модели весов (убедись, что best.pt лежит в этой же папке!)
print("🔄 Загрузка модели YOLOv11 на MacBook...")
model = YOLO("best.pt")
print("✅ Модель успешно загружена!")

# 3. Ответ на команду /start
@dp.message(Command("start"))
async def cmd_start(message: types.Message):
    await message.answer(
        "👋 Приветствую! Я система искусственного интеллекта для контроля ТБ на стройплощадке.\n\n"
        "📸 Отправьте мне фотографию со стройки, и я проверю наличие средств индивидуальной защиты (СИЗ)."
    )

# 4. Обработка входящих фотографий
@dp.message(F.photo)
async def handle_photo(message: types.Message):
    await message.answer("🔄 Нейросеть анализирует изображение, подождите...")
    
    # Скачиваем фото от пользователя
    photo = message.photo[-1] 
    file_info = await bot.get_file(photo.file_id)
    input_path = "temp_input.jpg"
    await bot.download_file(file_info.file_path, input_path)
    
    # Запускаем детекцию
    results = model.predict(source=input_path, save=True, conf=0.4)
    
    # Ищем путь к обработанной картинке
    saved_dir = results[0].save_dir
    predicted_path = os.path.join(saved_dir, "temp_input.jpg")
    
   # Инициализируем счетчики под все классы
    person_count = 0
    helmet_count = 0
    vest_count = 0
    none_count = 0  
    
    boxes = results[0].boxes
    
    # Считаем объекты строго по полному совпадению имени класса
    for box in boxes:
        class_id = int(box.cls[0])
        class_name = model.names[class_id].lower().strip() # очищаем от случайных пробелов
        
        # Используем строгое равенство == вместо проверки вхождения "in"
        if class_name == "person":
            person_count += 1
        elif class_name == "helmet":
            helmet_count += 1
        elif class_name == "vest":
            vest_count += 1
        elif class_name == "no_helmet" or class_name == "none":
            none_count += 1
            
   # 1. Считаем дефицит по каскам и жилетам на основе количества людей
    missing_helmets = max(0, person_count - helmet_count)
    missing_vests = max(0, person_count - vest_count)
    
    # 2. Считаем реальное количество людей-нарушителей
    if person_count > 0:
        calculated_violators = max(missing_helmets, missing_vests)
        if none_count > 0 and calculated_violators == 0:
            calculated_violators = min(person_count, none_count)
    else:
        calculated_violators = 0
        
    has_violations = calculated_violators > 0
    # ---------------------------------

    # Формируем красивый и подробный отчет
    report_text = "📊 **Отчет автоматического контроля ТБ:**\n\n"
    report_text += f"👷‍♂️ Всего сотрудников в кадре: {person_count} чел.\n"
    report_text += f"🪖 Обнаружено касок: {helmet_count} шт.\n"
    report_text += f"🦺 Обнаружено жилетов: {vest_count} шт.\n\n"
    
    if has_violations:
        report_text += f"⚠️ **ОБНАРУЖЕНЫ НАРУШЕНИЯ ТБ!**\n"
        report_text += f"❌ На площадке обнаружено нарушителей: {calculated_violators} чел.\n"
        report_text += f"🔍 Детализация дефицита СИЗ:\n"
        if missing_helmets > 0:
            report_text += f"   - Не хватает касок: {missing_helmets} шт.\n"
        if missing_vests > 0:
            report_text += f"   - Не хватает жилетов: {missing_vests} шт.\n"
            
        report_text += "\n❗ Информация зафиксирована в журнале нарушений и направлена дежурному инженеру."
    else:
        report_text += "✅ Нарушений не обнаружено. Все сотрудники находятся в полной экипировке СИЗ."

    # Отправляем готовую картинку с рамками и отчет пользователю обратно
    if os.path.exists(predicted_path):
        photo_to_send = types.FSInputFile(predicted_path)
        await message.answer_photo(photo=photo_to_send, caption=report_text, parse_mode="Markdown")
        
        # Если нарушения есть — РЕАЛЬНО отправляем аларм И ФОТО инженеру по ТБ
        if has_violations:
            try:
                alarm_text = (
                    f"🚨 **ТРЕВОГА ТБ!**\n"
                    f"На строительном объекте обнаружено нарушителей: {calculated_violators} чел.\n"
                    f"Срочно проверьте площадку!"
                )
                
                # Создаем объект файла заново для повторной отправки
                photo_for_officer = types.FSInputFile(predicted_path)
                
                # Отправляем инженеру фото СРАЗУ с тревожным описанием
                await bot.send_photo(
                    chat_id=SAFETY_OFFICER_ID, 
                    photo=photo_for_officer, 
                    caption=alarm_text, 
                    parse_mode="Markdown"
                )
                print("📣 Фото и уведомление инженеру успешно отправлены в Telegram!")
            except Exception as e:
                print(f"❌ Ошибка отправки уведомления инженеру: {e}")
    else:
        await message.answer("Ошибка при генерации изображения с результатами детекции.")
        
    # Удаляем временный исходный файл
    if os.path.exists(input_path): 
        os.remove(input_path)

# 5. Запуск процесса опроса сервера Telegram
async def main():
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())