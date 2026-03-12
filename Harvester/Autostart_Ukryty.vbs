Set WshShell = CreateObject("WScript.Shell")
WshShell.CurrentDirectory = "c:\Users\marek\.gemini\antigravity\scratch\tick scraper\dist"
WshShell.Run "TickHarvester.exe", 0, False
