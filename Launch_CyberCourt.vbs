Set WshShell = CreateObject("WScript.Shell")
WshShell.Run "cmd /c cd /d E:\CyberCourtSimulator && .venv\Scripts\activate && python app.py", 0, False
