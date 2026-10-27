PCB REPAIR WORKFLOW - OFFICE NETWORK VERSION

ONE-TIME SETUP (on the PC that will stay switched on)
1. Install Python 3 from python.org (tick "Add Python to PATH").
2. Unzip this folder anywhere, for example C:\pcb-workflow

START
- Windows: double-click start-windows.bat
- Mac/Linux: open a terminal in the folder and run: python3 server.py
The window prints an address like http://192.168.1.20:8000

USE
- On this PC open http://localhost:8000
- On any other PC or phone on the same Wi-Fi/LAN open the second address shown.
- The header shows "Office network: live, shared by everyone" when it works.
- Everyone sees the same jobs; the board refreshes every few seconds.

IF OTHER PCs CANNOT OPEN IT
- Allow Python through Windows Firewall (private network) when asked.
- Check both PCs are on the same network.

DATA AND BACKUP
- All jobs are stored in jobs.json in this folder. Copy that file to back up.
- To use another port: python server.py 8080

NOTES
- Anyone on your network can open and edit; there are no logins in this version.
- Works without internet.

PASSWORD (EDITING)
- Everyone can VIEW jobs. To add or change anything, click "Locked - Unlock to edit" and enter the password.
- The password is checked by the server (stored only as a salted hash). Wrong guesses are limited: 5 tries, then 1 minute wait.
- Editing stays unlocked in that browser tab for up to 8 hours.
- Change the password: stop the server, run  python server.py setpass  then start it again.
- On a plain office network the password travels unencrypted. Use only on a network you trust.

JOB ID
- The Job ID is typed by hand in the TRC Received form. It must be unique (letters, numbers, - . _ only, up to 40 characters).

IMAGES
- Images added in the PCB Received form are saved in the 'images' folder next to jobs.json. Back up BOTH jobs.json and the images folder.
- Up to 5 images per job; each is resized automatically.
