import os
import csv
from datetime import datetime

def generate_weekly_report(subject_name, week_number, students_data):
    """
    Generate a separate Excel (CSV) file for each subject based on the week number.
    :param subject_name: Name of the course
    :param week_number: Calculated week (1-15)
    :param students_data: List of dictionaries containing [ID, Name, Status]
    """
    
    # 1. Create a base directory for reports if it doesn't exist
    base_dir = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "Attendance_Reports")
    subject_dir = os.path.join(base_dir, subject_name)
    
    if not os.path.exists(subject_dir):
        os.makedirs(subject_dir)
        
    # 2. Construct the file name (e.g., AI_Course_Week_01.csv)
    file_name = f"{subject_name}_Week_{week_number:02d}.csv"
    file_path = os.path.join(subject_dir, file_name)
    
    # 3. Write data to the CSV file
    try:
        with open(file_path, mode='w', newline='', encoding='utf-8') as file:
            writer = csv.writer(file)
            
            # Header Row
            writer.writerow(['Student ID', 'Student Name', 'Date', 'Week', 'Status'])
            
            # Data Rows
            today_str = datetime.now().strftime("%Y-%m-%d")
            for student in students_data:
                writer.writerow([
                    student['id'], 
                    student['name'], 
                    today_str, 
                    f"Week {week_number}", 
                    student['status']
                ])
                
        print(f"[SUCCESS] Report generated: {file_path}")
        return file_path
    except Exception as e:
        print(f"[ERROR] Failed to generate report: {str(e)}")
        return None

# Example usage for testing:
# test_data = [{'id': '20101', 'name': 'Emad', 'status': 'Present'}]
# generate_weekly_report("Computer_Vision", 1, test_data)