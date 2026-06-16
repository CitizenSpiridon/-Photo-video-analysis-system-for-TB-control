import os
import asyncio
import cv2
import time
from ultralytics import YOLO
from aiogram import Bot
from aiogram.types import FSInputFile

# 1. Настройки подключения к Telegram и ID инженера
API_TOKEN = '8973144207:AAHwDI2q0r04ESAyVGTFUtn11ZeIjmKMDYs'
SAFETY_OFFICER_ID = 509182730

bot = Bot(token=API_TOKEN)

# 2. Загрузка модели весов
print("🔄 Загрузка модели YOLOv11...")
model = YOLO("best.pt")
print("✅ Модель успешно загружена!")

# Интервал проверки в секундах
INTERVAL = 10 

async def main_monitoring():
    # Подключение к веб-камере MacBook (0 — FaceTime камера)
    cap = cv2.VideoCapture(0)
    
    if not cap.isOpened():
        print("❌ Ошибка: Не удалось получить доступ к веб-камере Мака!")
        return

    print("📹 Асинхронный мониторинг ТБ запущен.")
    print(f"⏱️ Интервал проверки: каждые {INTERVAL} секунд. Для выхода: Ctrl + C.\n")

    try:
        while True:
            # СБРОС БУФЕРА КАМЕРЫ: читаем несколько кадров «вхолостую»
            for _ in range(5):
                cap.grab()
            
            # Делаем реальный снимок
            ret, frame = cap.read()
            if not ret:
                print("❌ Ошибка захвата кадра с камеры. Пробуем снова...")
                await asyncio.sleep(2)
                continue
                
            current_time = time.strftime('%H:%M:%S')
            print(f"📸 [{current_time}] Свежий кадр захвачен. Анализируем...")
            
            # Сохраняем во временный файл
            temp_frame_path = "live_snapshot.jpg"
            cv2.imwrite(temp_frame_path, frame)
            
            # Прогон через YOLO с порогом уверенности 0.45
            results = model.predict(source=temp_frame_path, save=True, conf=0.40, verbose=False)
            
            # Путь к размеченному кадру
            saved_dir = results[0].save_dir
            predicted_path = os.path.join(saved_dir, "live_snapshot.jpg")
            
            # Инициализируем счетчики под все классы
            person_count = 0
            helmet_count = 0
            vest_count = 0
            none_count = 0  
            
            boxes = results[0].boxes
            
            # Считаем объекты строго по полному совпадению имени класса
            for box in boxes:
                class_id = int(box.cls[0])
                class_name = model.names[class_id].lower().strip()
                
                if class_name == "person":
                    person_count += 1
                elif class_name == "helmet":
                    helmet_count += 1
                elif class_name == "vest":
                    vest_count += 1
                elif class_name == "no_helmet" or class_name == "none":
                    none_count += 1
            
            missing_helmets = max(0, person_count - helmet_count)
            missing_vests = max(0, person_count - vest_count)
            
            if person_count > 0:
                calculated_violators = max(missing_helmets, missing_vests)
                if none_count > 0 and calculated_violators == 0:
                    calculated_violators = min(person_count, none_count)
            else:
                calculated_violators = 0
                
            has_violations = calculated_violators > 0
            # ---------------------------------
            
            if has_violations:
                print(f"⚠️ [{current_time}] ОБНАРУЖЕНО НАРУШЕНИЕ! Нарушителей: {calculated_violators}. Отправляю аларм...")
                
                alarm_text = (
                    f"🚨 **👑 ТРЕВОГА ТБ С ВИДЕОПОТОКА!**\n"
                    f"⏱️ Время фиксации: {current_time}\n"
                    f"👷‍♂️ Сотрудников в кадре: {person_count} чел.\n"
                    f"❌ Нарушителей без СИЗ: {calculated_violators} чел.\n"
                )
                if missing_helmets > 0: 
                    alarm_text += f"   - Дефицит касок: {missing_helmets} шт.\n"
                if missing_vests > 0: 
                    alarm_text += f"   - Дефицит жилетов: {missing_vests} шт.\n"
                
                try:
                    if os.path.exists(predicted_path):
                        await bot.send_photo(
                            chat_id=SAFETY_OFFICER_ID, 
                            photo=FSInputFile(predicted_path), 
                            caption=alarm_text, 
                            parse_mode="Markdown"
                        )
                        print("📣 Уведомление успешно отправлено в Telegram!")
                except Exception as e:
                    print(f"❌ Ошибка отправки в Telegram: {e}")
            else:
                print(f"✅ [{current_time}] Нарушений нет. (Людей: {person_count}, Касок: {helmet_count}, Жилетов: {vest_count})")
                
            if os.path.exists(temp_frame_path):
                os.remove(temp_frame_path)
                
            # Асинхронно засыпаем строго на заданный интервал
            await asyncio.sleep(INTERVAL)

    except KeyboardInterrupt:
        print("\n🛑 Мониторинг остановлен пользователем.")
    finally:
        cap.release()
        await bot.session.close()
        print("📹 Камера успешно отключена, seссия бота закрыта.")

if __name__ == "__main__":
    try:
        asyncio.run(main_monitoring())
    except KeyboardInterrupt:
        print("\n🛑 Программа завершена.")