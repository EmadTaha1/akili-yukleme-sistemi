import sys
import os

sys.setrecursionlimit(5000)
sys.path.append(os.path.abspath(os.path.dirname(__file__)))

from ui.main_dashboard import AttendanceApp

if __name__ == "__main__":
    app = AttendanceApp()
    app.mainloop()
