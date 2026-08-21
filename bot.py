print("IL FILE STA PARTENDO!")
import anthropic
import requests
import datetime
import json
import os
import asyncio
from telegram import Update
from telegram.ext import ApplicationBuilder, MessageHandler, filters, ContextTypes
import yfinance as yf
print("IMPORT COMPLETATI!")

ANTHROPIC_API_KEY = os.environ.get("ANTHROPIC_API_KEY")
TELEGRAM_TOKEN = os.environ.get("TELEGRAM_TOKEN")
print("TOKEN ANTHROPIC:", ANTHROPIC_API_KEY is not None)
print("TOKEN TELEGRAM:", TELEGRAM_TOKEN is not None)

client = anthropic.Anthropic(api_key=ANTHROPIC_API_KEY)
print("CLIENT CREATO!")

FILE_PROMEMORIA = "promemoria.json"
FILE_ALERT_TITOLI = "alert_titoli.json"

if not os.path.exists(FILE_PROMEMORIA):
    with open(FILE_PROMEMORIA, "w") as f:
        json.dump([], f)

if not os.path.exists(FILE_ALERT_TITOLI):
    with open(FILE_ALERT_TITOLI, "w") as f:
        json.dump([], f)


def che_ore_sono():
    adesso = datetime.datetime.now()
    ora_italiana = adesso + datetime.timedelta(hours=2)
    return "Sono le " + str(ora_italiana.hour) + ":" + str(ora_italiana.minute)


def data_oggi():
    adesso = datetime.datetime.now()
    return str(adesso.year) + "-" + str(adesso.month).zfill(2) + "-" + str(adesso.day).zfill(2)


def controlla_meteo(citta):
    url_coordinate = "https://geocoding-api.open-meteo.com/v1/search?name=" + citta + "&count=1&language=it"
    risposta_coord = requests.get(url_coordinate)
    dati_coord = risposta_coord.json()
    lat = dati_coord["results"][0]["latitude"]
    lon = dati_coord["results"][0]["longitude"]
    url_meteo = "https://api.open-meteo.com/v1/forecast?latitude=" + str(lat) + "&longitude=" + str(lon) + "&current=temperature_2m,precipitation&timezone=Europe/Rome"
    risposta_meteo = requests.get(url_meteo)
    dati_meteo = risposta_meteo.json()
    temperatura = dati_meteo["current"]["temperature_2m"]
    pioggia = dati_meteo["current"]["precipitation"]
    return "A " + citta + ": " + str(temperatura) + "C, Pioggia: " + str(pioggia) + "mm"


def salva_promemoria(evento, data, ora):
    with open(FILE_PROMEMORIA, "r") as f:
        promemoria = json.load(f)
    nuovo = {"evento": evento, "data": data, "ora": ora, "alert_24h": False, "alert_1h": False}
    promemoria.append(nuovo)
    with open(FILE_PROMEMORIA, "w") as f:
        json.dump(promemoria, f, indent=2)
    return "Promemoria salvato! Ti ricordero " + evento + " il " + data + " alle " + ora


def prezzo_titolo(simbolo):
    titolo = yf.Ticker(simbolo)
    dati = titolo.history(period="1d")
    prezzo = dati["Close"].iloc[-1]
    return round(prezzo, 2)


def salva_alert_titolo(simbolo, soglia, direzione):
    with open(FILE_ALERT_TITOLI, "r") as f:
        alert = json.load(f)
    nuovo = {"simbolo": simbolo, "soglia": soglia, "direzione": direzione, "attivato": False}
    alert.append(nuovo)
    with open(FILE_ALERT_TITOLI, "w") as f:
        json.dump(alert, f, indent=2)
    return "Alert salvato! Ti avviso quando " + simbolo + " va " + direzione + " " + str(soglia)


def mostra_alert_titoli():
    with open(FILE_ALERT_TITOLI, "r") as f:
        alert = json.load(f)
    attivi = [a for a in alert if not a["attivato"]]
    if len(attivi) == 0:
        return "Non hai nessun alert attivo al momento."
    testo = "I tuoi alert attivi:\n"
    for a in attivi:
        testo += "- " + a["simbolo"] + " " + a["direzione"] + " " + str(a["soglia"]) + "$\n"
    return testo


def cancella_alert_titolo(simbolo):
    with open(FILE_ALERT_TITOLI, "r") as f:
        alert = json.load(f)
    nuovi = [a for a in alert if a["simbolo"].upper() != simbolo.upper()]
    with open(FILE_ALERT_TITOLI, "w") as f:
        json.dump(nuovi, f, indent=2)
    return "Alert su " + simbolo + " cancellati!"


tools = [
    {"name": "che_ore_sono", "description": "Usa questo tool quando l utente chiede che ore sono", "input_schema": {"type": "object", "properties": {}, "required": []}},
    {"name": "data_oggi", "description": "Usa questo tool quando hai bisogno della data di oggi o quando l utente dice domani, dopodomani, tra X giorni", "input_schema": {"type": "object", "properties": {}, "required": []}},
    {"name": "controlla_meteo", "description": "Usa questo tool per qualsiasi domanda sul meteo", "input_schema": {"type": "object", "properties": {"citta": {"type": "string", "description": "Il nome della citta"}}, "required": ["citta"]}},
    {"name": "salva_promemoria", "description": "Usa questo tool quando l utente vuole salvare un promemoria o appuntamento", "input_schema": {"type": "object", "properties": {"evento": {"type": "string", "description": "Il nome dell evento"}, "data": {"type": "string", "description": "La data in formato YYYY-MM-DD"}, "ora": {"type": "string", "description": "L ora in formato HH:MM"}}, "required": ["evento", "data", "ora"]}},
    {"name": "prezzo_titolo", "description": "Usa questo tool quando l utente chiede il prezzo attuale di un azione o crypto. Simbolo in formato ticker: Apple=AAPL, Tesla=TSLA, Bitcoin=BTC-USD, Ferrari=RACE.MI", "input_schema": {"type": "object", "properties": {"simbolo": {"type": "string", "description": "Il ticker del titolo"}}, "required": ["simbolo"]}},
    {"name": "salva_alert_titolo", "description": "Usa questo tool quando l utente vuole essere avvisato se un titolo sale sopra o scende sotto un certo prezzo", "input_schema": {"type": "object", "properties": {"simbolo": {"type": "string", "description": "Il ticker del titolo"}, "soglia": {"type": "number", "description": "Il prezzo soglia"}, "direzione": {"type": "string", "description": "sopra oppure sotto"}}, "required": ["simbolo", "soglia", "direzione"]}},
    {"name": "mostra_alert_titoli", "description": "Usa questo tool quando l utente vuole vedere la lista dei suoi alert attivi sui titoli", "input_schema": {"type": "object", "properties": {}, "required": []}},
    {"name": "cancella_alert_titolo", "description": "Usa questo tool quando l utente vuole cancellare un alert su un titolo", "input_schema": {"type": "object", "properties": {"simbolo": {"type": "string", "description": "Il ticker del titolo da cancellare"}}, "required": ["simbolo"]}}
]

conversazione = []


def agente(messaggio):
    conversazione.clear()
    conversazione.append({"role": "user", "content": messaggio})
    testo = ""
    for _ in range(5):
        risposta = client.messages.create(
            model="claude-sonnet-4-5",
            max_tokens=1024,
            system="Sei l assistente personale di Cecilia che vive a Ravenna. Sei gentile e simpatico. Conosci il suo gatto che si chiama Pixel. Rispondi sempre in italiano. Usa SEMPRE i tools disponibili quando servono. Non dire mai che non puoi fare qualcosa se hai un tool per farlo. Non dire mai di andare su siti esterni.",
            tools=tools,
            messages=conversazione
        )
        if risposta.stop_reason == "tool_use":
            tool_results = []
            for block in risposta.content:
                if block.type == "tool_use":
                    if block.name == "che_ore_sono":
                        risultato = che_ore_sono()
                    elif block.name == "data_oggi":
                        risultato = data_oggi()
                    elif block.name == "controlla_meteo":
                        risultato = controlla_meteo(block.input["citta"])
                    elif block.name == "salva_promemoria":
                        risultato = salva_promemoria(block.input["evento"], block.input["data"], block.input["ora"])
                    elif block.name == "prezzo_titolo":
                        risultato = str(prezzo_titolo(block.input["simbolo"]))
                    elif block.name == "salva_alert_titolo":
                        risultato = salva_alert_titolo(block.input["simbolo"], block.input["soglia"], block.input["direzione"])
                    elif block.name == "mostra_alert_titoli":
                        risultato = mostra_alert_titoli()
                    elif block.name == "cancella_alert_titolo":
                        risultato = cancella_alert_titolo(block.input["simbolo"])
                    else:
                        risultato = "Tool non trovato"
                    tool_results.append({"type": "tool_result", "tool_use_id": block.id, "content": risultato})
            conversazione.append({"role": "assistant", "content": risposta.content})
            conversazione.append({"role": "user", "content": tool_results})
        else:
            testo = risposta.content[0].text
            break
    conversazione.append({"role": "assistant", "content": testo})
    return testo


async def controlla_alert_promemoria(bot, chat_id):
    while True:
        try:
            with open(FILE_PROMEMORIA, "r") as f:
                promemoria = json.load(f)
            adesso = datetime.datetime.now() + datetime.timedelta(hours=2)
            modificato = False
            for p in promemoria:
                data_ora = datetime.datetime.strptime(p["data"] + " " + p["ora"], "%Y-%m-%d %H:%M")
                diff = data_ora - adesso
                ore_mancanti = diff.total_seconds() / 3600
                if 23.5 <= ore_mancanti <= 24.5 and not p["alert_24h"]:
                    await bot.send_message(chat_id=chat_id, text="Domani hai: " + p["evento"] + " alle " + p["ora"] + "!")
                    p["alert_24h"] = True
                    modificato = True
                if 0.5 <= ore_mancanti <= 1.5 and not p["alert_1h"]:
                    await bot.send_message(chat_id=chat_id, text="Tra 1 ora hai: " + p["evento"] + " alle " + p["ora"] + "!")
                    p["alert_1h"] = True
                    modificato = True
            if modificato:
                with open(FILE_PROMEMORIA, "w") as f:
                    json.dump(promemoria, f, indent=2)
        except Exception as e:
            print("Errore alert promemoria: " + str(e))
        await asyncio.sleep(1800)


async def controlla_alert_titoli(bot, chat_id):
    while True:
        try:
            with open(FILE_ALERT_TITOLI, "r") as f:
                alert = json.load(f)
            modificato = False
            for a in alert:
                if a["attivato"]:
                    continue
                prezzo_attuale = prezzo_titolo(a["simbolo"])
                scatta = False
                if a["direzione"] == "sotto" and prezzo_attuale <= a["soglia"]:
                    scatta = True
                elif a["direzione"] == "sopra" and prezzo_attuale >= a["soglia"]:
                    scatta = True
                if scatta:
                    await bot.send_message(chat_id=chat_id, text="ALERT! " + a["simbolo"] + " e a " + str(prezzo_attuale) + "$ (" + a["direzione"] + " " + str(a["soglia"]) + "$)!")
                    a["attivato"] = True
                    modificato = True
            if modificato:
                with open(FILE_ALERT_TITOLI, "w") as f:
                    json.dump(alert, f, indent=2)
        except Exception as e:
            print("Errore alert titoli: " + str(e))
        await asyncio.sleep(1800)


chat_id_cecilia = None
alert_avviato = False


async def rispondi(update: Update, context: ContextTypes.DEFAULT_TYPE):
    global chat_id_cecilia, alert_avviato
    chat_id_cecilia = update.effective_chat.id
    if not alert_avviato:
        alert_avviato = True
        asyncio.ensure_future(controlla_alert_promemoria(context.bot, chat_id_cecilia))
        asyncio.ensure_future(controlla_alert_titoli(context.bot, chat_id_cecilia))
        print("Alert avviati per chat_id: " + str(chat_id_cecilia))
    messaggio = update.message.text
    risposta_agente = agente(messaggio)
    await update.message.reply_text(risposta_agente)


async def main():
    app = ApplicationBuilder().token(TELEGRAM_TOKEN).build()
    app.add_handler(MessageHandler(filters.TEXT, rispondi))
    print("Bot avviato!")
    await app.run_polling(drop_pending_updates=True)


if __name__ == "__main__":
    print("STO PER AVVIARE MAIN!")
    asyncio.run(main())
