import sys
import os

sys.setrecursionlimit(5000)
sys.path.append(os.path.abspath(os.path.dirname(__file__)))

from ui.main_dashboard import AttendanceApp

from ui.gui_login import LoginWindow

teacher_data = None

def on_login_success(teacher_info, login_window):
    global teacher_data
    teacher_data = teacher_info
    login_window.quit()  # Break out of the mainloop safely

if __name__ == "__main__":
    login_app = LoginWindow(on_login_success)
    login_app.mainloop()
    
    # Safely destroy the login window after its mainloop ends
    try:
        login_app.destroy()
    except Exception:
        pass
    
    # If login was successful, start the dashboard
    if teacher_data:
        app = AttendanceApp(teacher_data)
        app.mainloop()
