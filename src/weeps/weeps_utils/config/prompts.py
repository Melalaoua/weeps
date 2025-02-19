from datetime import datetime
import pytz

class Prompts:
    persona = "Your name is Weeps. You are a helpful AI assistant."

    paris_timezone = pytz.timezone('Europe/Paris')
    now = datetime.now(paris_timezone)
        
    prompt_system = [f"Date of day (DD/MM/YYYY): {now.strftime("%d/%m/%Y")}", f"Hour of the day : {now.strftime("%H:%M")}.", persona]
