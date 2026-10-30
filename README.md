# 🚗 Tesla Pronta Consegna Watcher (Model Y & Model 3)

Dieser Watcher überwacht automatisch die italienischen Tesla-Bestandsseiten (**Pronta Consegna**, PLZ `39100` Bozen / Italien) für **neuwertige („new“)** Fahrzeuge:
- **Model Y:** [https://www.tesla.com/it_IT/inventory/new/my?arrangeby=plh&zip=39100&range=0](https://www.tesla.com/it_IT/inventory/new/my?arrangeby=plh&zip=39100&range=0)
- **Model 3:** [https://www.tesla.com/it_IT/inventory/new/m3?arrangeby=plh&zip=39100&range=0](https://www.tesla.com/it_IT/inventory/new/m3?arrangeby=plh&zip=39100&range=0)

Sobald ein neues Fahrzeug gelistet wird, erhältst du sofort eine E-Mail mit Preis, Ausstattung, Standort, VIN und Direkt-Bestelllink an **`aperathoner@gmail.com`**. Bereits gemeldete Fahrzeuge werden in `seen_vehicles.json` gespeichert, damit du keine doppelten E-Mails bekommst.

---

## 🔑 Schritt 1: Gmail App-Passwort erstellen (einmalig, 1 Minute)

Damit das Skript E-Mails über dein Gmail-Konto versenden darf, benötigst du ein **16-stelliges Google App-Passwort**:
1. Öffne [https://myaccount.google.com/apppasswords](https://myaccount.google.com/apppasswords) (die 2-Faktor-Authentifizierung muss in deinem Google-Konto aktiviert sein).
2. Gib als App-Namen z. B. `Tesla Watcher` ein und klicke auf **Erstellen**.
3. Kopiere das angezeigte 16-stellige Passwort (ohne Leerzeichen).

---

## ☁️ Option A: 24/7 kostenlos in der Cloud ausführen (auch wenn dein PC ausgeschaltet ist!)

Über **GitHub Actions** läuft das Skript völlig kostenlos alle ~10 Minuten auf einem Cloud-Server von GitHub:

1. **Kostenloses GitHub-Repository anlegen:**
   - Gehe auf [https://github.com/new](https://github.com/new) und erstelle ein neues Repository (z. B. `tesla-watcher`).
   - Lade alle Dateien aus diesem Ordner `C:\Users\Alex\TeslaWatcher` (außer `.env`) hoch – oder führe im Terminal in diesem Ordner folgende Befehle aus:
     ```powershell
     git init
     git add .
     git commit -m "Initial commit"
     git branch -M main
     git remote add origin https://github.com/DEIN_USERNAME/tesla-watcher.git
     git push -u origin main
     ```
2. **Zugangsdaten sicher als GitHub Secrets hinterlegen:**
   - Öffne in deinem GitHub-Repository **Settings** → **Secrets and variables** → **Actions** → **New repository secret**.
   - Lege folgende **2 Secrets** an:
     - `SMTP_USER` = `aperathoner@gmail.com`
     - `SMTP_PASSWORD` = *(dein 16-stelliges Gmail App-Passwort)*
3. **Aktivieren & Testen:**
   - Klicke oben im Repository auf den Reiter **Actions**, wähle links **Tesla Pronta Consegna Watcher** und klicke auf **Run workflow**. Ab sofort prüft der Server automatisch alle 10 Minuten rund um die Uhr!

---

## 💻 Option B: Lokal auf deinem Windows-PC ausführen

1. Öffne die Datei [`.env`](file:///C:/Users/Alex/TeslaWatcher/.env) in diesem Ordner mit dem Editor (Notepad) und trage bei `SMTP_PASSWORD=` dein 16-stelliges Gmail App-Passwort ein.
2. **Test-E-Mail senden:** Doppelklicke auf [`test_email.bat`](file:///C:/Users/Alex/TeslaWatcher/test_email.bat) – du erhältst sofort eine Test-E-Mail an `aperathoner@gmail.com`.
3. **Überwachung starten:**
   - **Per Doppelklick:** Starte [`start_watcher.bat`](file:///C:/Users/Alex/TeslaWatcher/start_watcher.bat) (prüft alle 10 Minuten).
   - **Oder automatisch im Windows-Hintergrund:** Rechtsklick auf [`setup_windows_task.ps1`](file:///C:/Users/Alex/TeslaWatcher/setup_windows_task.ps1) → *Mit PowerShell ausführen*. Dadurch wird eine Aufgabe in der Windows-Aufgabenplanung angelegt, die alle 10 Minuten unsichtbar im Hintergrund prüft.
