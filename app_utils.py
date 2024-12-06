import asyncio
import traceback
from datetime import datetime, timedelta

async def get_room_id(bot, room_alias_or_id):
    try:
        # Если строка начинается с "!", это ID комнаты — возвращаем его напрямую
        if room_alias_or_id.startswith("!"):
            return room_alias_or_id
        # Если это alias, выполняем join и возвращаем ID комнаты
        response = await bot.async_client.join(room_alias_or_id)
        return response.room_id
    except Exception as e:
        print(f"Ошибка при получении room_id: {e}")
        return None

# Функция для отправки сообщения
async def send_message_local(bot, room_id, message):
    try:
        await bot.api.send_text_message(room_id, message)
        print(f"Сообщение отправлено в комнату {room_id}: {message}")
    except Exception as e:
        print(f"Ошибка при отправке сообщения: {traceback.format_exc()}")

# Функция для запуска задач отправки сообщений
async def send_messages(bot, task, task_status, task_id):
    print(send_messages)
    print(task["room_id"])
    room_id = await get_room_id(bot, task["room_id"])
    if not room_id:
        return

    while True:
        try:
            if task_status[task_id] != "active":
                print(f"Задача находится в статусе '{task_status}'. Ожидание активации.")
                await asyncio.sleep(60)  # Ждем перед следующей проверкой
                continue
            print("time")
            current_datetime = datetime.now() + timedelta(hours=2)
            current_time = current_datetime.time()
            print(task['start_time'])
            print(task['end_time'])
            print(current_time)

            rec_start_time = datetime.strptime(str(task['start_time']), "%H:%M:%S").time() if task['start_time'] else None
            rec_end_time = datetime.strptime(str(task['end_time']), "%H:%M:%S").time() if task['end_time'] else None

            if (task.get("always_on", True) or
                    (rec_start_time <= current_time <= rec_end_time)):
                print("time works")
                await send_message_local(bot, room_id, task["message"])
        except Exception as e:
            print(traceback.format_exc())
        await asyncio.sleep(task["interval"] * 60)
