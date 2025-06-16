import streamlit as st
import psycopg2
from psycopg2.extras import RealDictCursor
import google.generativeai as genai
import json
import time
import tempfile
import os
from datetime import datetime
import random
import string
import re

DB_CONFIG = {
    'host': 'localhost',
    'database': 'AI_2',
    'user': 'postgres',
    'password': '123456',
    'port': '5432'
}

st.set_page_config(page_title="Adaptive Quiz & Course System", layout="wide")

GEMINI_API_KEY_QUIZ = "API KEY"
GEMINI_API_KEY_VIVA = "API KEY"

# Predefined courses
AVAILABLE_COURSES = ["Python", "Data Science", "Machine Learning"]

def validate_email(email):
    """Validate email format"""
    pattern = r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$'
    return re.match(pattern, email) is not None

def get_db_connection():
    """Create and return a database connection"""
    try:
        conn = psycopg2.connect(**DB_CONFIG)
        return conn
    except psycopg2.Error as e:
        st.error(f"Database connection error: {e}")
        return None

def create_login_table():
    """Create login table"""
    conn = get_db_connection()
    if conn is None:
        return False
    try:
        cursor = conn.cursor()
        create_login_query = """
        CREATE TABLE IF NOT EXISTS user_login (
            id SERIAL PRIMARY KEY,
            email VARCHAR(255) UNIQUE NOT NULL,
            password VARCHAR(255) NOT NULL,
            total_logins INTEGER DEFAULT 0,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            last_login TIMESTAMP
        );"""
        
        cursor.execute(create_login_query)
        conn.commit()
        cursor.close()
        conn.close()
        return True
    except psycopg2.Error as e:
        st.error(f"Error creating login table: {e}")
        if conn:
            conn.close()
        return False

def register_user(email, password):
    """Register new user"""
    if not validate_email(email):
        return False, "Invalid email format"
    
    conn = get_db_connection()
    if conn is None:
        return False, "Database connection error"
    
    try:
        cursor = conn.cursor()
        cursor.execute("SELECT email FROM user_login WHERE email = %s", (email,))
        if cursor.fetchone():
            cursor.close()
            conn.close()
            return False, "Email already registered"
        
        cursor.execute("""
            INSERT INTO user_login (email, password) 
            VALUES (%s, %s)
        """, (email, password))
        
        conn.commit()
        cursor.close()
        conn.close()
        return True, "Registration successful"
    except psycopg2.Error as e:
        if conn:
            conn.close()
        return False, f"Registration error: {e}"

def login_user(email, password):
    """Login user"""
    conn = get_db_connection()
    if conn is None:
        return False, "Database connection error"
    
    try:
        cursor = conn.cursor()
        cursor.execute("""
            SELECT email, password FROM user_login 
            WHERE email = %s AND password = %s
        """, (email, password))
        
        user = cursor.fetchone()
        if user:
            cursor.execute("""
                UPDATE user_login 
                SET total_logins = total_logins + 1, last_login = CURRENT_TIMESTAMP 
                WHERE email = %s
            """, (email,))
            conn.commit()
            cursor.close()
            conn.close()
            return True, "Login successful"
        else:
            cursor.close()
            conn.close()
            return False, "Invalid email or password"
    except psycopg2.Error as e:
        if conn:
            conn.close()
        return False, f"Login error: {e}"

def login_page():
    """Display login page"""
    st.title("🔐 Login to Adaptive Quiz System")
    
    tab1, tab2 = st.tabs(["Login", "Register"])
    
    with tab1:
        st.header("Login")
        with st.form("login_form"):
            email = st.text_input("Email:")
            password = st.text_input("Password:", type="password")
            
            if st.form_submit_button("Login"):
                if email and password:
                    success, message = login_user(email, password)
                    if success:
                        st.session_state.logged_in = True
                        st.session_state.user_email = email
                        st.success(message)
                        st.rerun()
                    else:
                        st.error(message)
                else:
                    st.error("Please fill in all fields")
    
    with tab2:
        st.header("Register New Account")
        with st.form("register_form"):
            reg_email = st.text_input("Email:", key="reg_email")
            reg_password = st.text_input("Password:", type="password", key="reg_password")
            confirm_password = st.text_input("Confirm Password:", type="password")
            
            if st.form_submit_button("Register"):
                if reg_email and reg_password and confirm_password:
                    if not validate_email(reg_email):
                        st.error("Please enter a valid email address")
                    elif reg_password != confirm_password:
                        st.error("Passwords do not match")
                    elif len(reg_password) < 6:
                        st.error("Password must be at least 6 characters long")
                    else:
                        success, message = register_user(reg_email, reg_password)
                        if success:
                            st.success(message + " Please login with your credentials.")
                        else:
                            st.error(message)
                else:
                    st.error("Please fill in all fields")

def generate_roll_no(domain, branch="CSE"):
    """Generate sequential roll number based on domain"""
    current_year = datetime.now().year % 100
    
    domain_codes = {
        "python": "PY",
        "data science": "DS", 
        "machine learning": "ML"
    }
    
    domain_lower = domain.lower()
    course_code = domain_codes.get(domain_lower, "GN")
    
    conn = get_db_connection()
    if conn:
        try:
            cursor = conn.cursor()
            pattern = f"{current_year}{course_code}%{branch}"
            cursor.execute("""
                SELECT roll_no FROM pre_assessment 
                WHERE roll_no LIKE %s 
                ORDER BY roll_no DESC LIMIT 1
            """, (pattern,))
            result = cursor.fetchone()
            
            if result:
                last_roll = result[0]
                seq_part = last_roll.split(course_code)[1][:3]
                next_seq = int(seq_part) + 1
            else:
                next_seq = 1
            
            cursor.close()
            conn.close()
            
            roll_no = f"{current_year}{course_code}{next_seq:03d}{branch}"
            return roll_no
            
        except Exception as e:
            st.error(f"Error generating roll number: {e}")
            if conn:
                conn.close()
            return f"{current_year}{course_code}001{branch}"
    
    return f"{current_year}{course_code}001{branch}"

def create_tables():
    """Create database tables"""
    conn = get_db_connection()
    if conn is None:
        return False
    try:
        cursor = conn.cursor()
        
        create_pre_assessment_query = """
        CREATE TABLE IF NOT EXISTS pre_assessment (
            roll_no VARCHAR(20) PRIMARY KEY,
            date TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            name VARCHAR(255) NOT NULL,
            domain VARCHAR(255) NOT NULL,
            hours_per_day INTEGER DEFAULT 3,
            weeks INTEGER DEFAULT 4,
            knowledge_scale INTEGER,
            current_week_no INTEGER DEFAULT 1,
            cognitive_score INTEGER DEFAULT 0,
            cognitive_iq INTEGER DEFAULT 0,
            domain_score INTEGER DEFAULT 0,
            domain_iq INTEGER DEFAULT 0,
            viva_score INTEGER DEFAULT 0,
            viva_response TEXT DEFAULT '',
            course_configured BOOLEAN DEFAULT FALSE
        );"""
        
        create_week_quiz_query = """
        CREATE TABLE IF NOT EXISTS week_quiz (
            id SERIAL PRIMARY KEY,
            roll_no VARCHAR(20) REFERENCES pre_assessment(roll_no) ON DELETE CASCADE,
            week_no INTEGER NOT NULL,
            week_quiz_score INTEGER DEFAULT 0,
            week_quiz_iq INTEGER DEFAULT 0,
            strong_areas TEXT,
            weak_areas TEXT,
            analysis TEXT,
            date TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            UNIQUE(roll_no, week_no)
        );"""
        
        create_course_content_query = """
        CREATE TABLE IF NOT EXISTS course_content (
            id SERIAL PRIMARY KEY,
            roll_no VARCHAR(20) REFERENCES pre_assessment(roll_no) ON DELETE CASCADE,
            week_no INTEGER NOT NULL,
            course_content TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            UNIQUE(roll_no, week_no)
        );"""
        
        create_overall_performance_query = """
        CREATE TABLE IF NOT EXISTS overall_performance (
            roll_no VARCHAR(20) PRIMARY KEY REFERENCES pre_assessment(roll_no) ON DELETE CASCADE,
            topics_excellented TEXT,
            outcome_of_course TEXT,
            student_progress TEXT,
            last_updated TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        );"""
        
        cursor.execute(create_pre_assessment_query)
        cursor.execute(create_week_quiz_query)
        cursor.execute(create_course_content_query)
        cursor.execute(create_overall_performance_query)
        conn.commit()
        cursor.close()
        conn.close()
        return True
    except psycopg2.Error as e:
        st.error(f"Error creating tables: {e}")
        if conn:
            conn.close()
        return False

def get_quiz_model():
    genai.configure(api_key=GEMINI_API_KEY_QUIZ)
    return genai.GenerativeModel('gemini-2.0-flash')

def get_viva_model():
    genai.configure(api_key=GEMINI_API_KEY_VIVA)
    return genai.GenerativeModel('gemini-2.0-flash')

def save_pre_assessment(data):
    """Save pre-assessment data to database"""
    conn = get_db_connection()
    if conn is None:
        return None
    try:
        roll_no = generate_roll_no(data['domain'])
        cursor = conn.cursor()
        
        insert_query = """
        INSERT INTO pre_assessment (
            roll_no, name, domain, hours_per_day, weeks, knowledge_scale,
            current_week_no, cognitive_score, cognitive_iq, domain_score, domain_iq
        ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
        """
        
        cursor.execute(insert_query, (
            roll_no,
            data.get('name', ''),
            data.get('domain', ''),
            data.get('hours_per_day', 3),
            data.get('weeks', 4),
            data.get('knowledge_scale', 2),
            1,
            data.get('cognitive_score', 0),
            data.get('cognitive_iq', 0),
            data.get('domain_score', 0),
            data.get('domain_iq', 0)
        ))
        
        cursor.execute("""
            INSERT INTO overall_performance (roll_no, topics_excellented, outcome_of_course, student_progress)
            VALUES (%s, %s, %s, %s)
        """, (roll_no, '', 'Course started', 'Initial assessment completed'))
        
        conn.commit()
        cursor.close()
        conn.close()
        return roll_no
    except psycopg2.Error as e:
        st.error(f"Error saving pre-assessment: {e}")
        if conn:
            conn.close()
        return None

def update_course_config(roll_no, hours_per_day, weeks):
    """Update course configuration"""
    conn = get_db_connection()
    if conn is None:
        return False
    try:
        cursor = conn.cursor()
        cursor.execute("""
            UPDATE pre_assessment 
            SET hours_per_day = %s, weeks = %s, course_configured = TRUE
            WHERE roll_no = %s
        """, (hours_per_day, weeks, roll_no))
        conn.commit()
        cursor.close()
        conn.close()
        return True
    except psycopg2.Error as e:
        st.error(f"Error updating course config: {e}")
        if conn:
            conn.close()
        return False

def update_current_week(roll_no, week_no):
    """Update current week number"""
    conn = get_db_connection()
    if conn is None:
        return False
    try:
        cursor = conn.cursor()
        cursor.execute("""
            UPDATE pre_assessment 
            SET current_week_no = %s 
            WHERE roll_no = %s
        """, (week_no, roll_no))
        conn.commit()
        cursor.close()
        conn.close()
        return True
    except psycopg2.Error as e:
        st.error(f"Error updating current week: {e}")
        if conn:
            conn.close()
        return False

def update_cognitive_scores(roll_no, cognitive_score, cognitive_iq):
    """Update cognitive score and IQ in database"""
    conn = get_db_connection()
    if conn is None:
        return False
    try:
        cursor = conn.cursor()
        cursor.execute("""
            UPDATE pre_assessment 
            SET cognitive_score = %s, cognitive_iq = %s 
            WHERE roll_no = %s
        """, (cognitive_score, cognitive_iq, roll_no))
        conn.commit()
        cursor.close()
        conn.close()
        
        # Update overall performance after cognitive assessment
        analyze_and_update_performance(roll_no)
        return True
        
    except psycopg2.Error as e:
        st.error(f"Error updating cognitive scores: {e}")
        if conn:
            conn.close()
        return False

def update_domain_scores(roll_no, domain_score, domain_iq):
    """Update domain score and IQ in database"""
    conn = get_db_connection()
    if conn is None:
        return False
    try:
        cursor = conn.cursor()
        cursor.execute("""
            UPDATE pre_assessment 
            SET domain_score = %s, domain_iq = %s 
            WHERE roll_no = %s
        """, (domain_score, domain_iq, roll_no))
        conn.commit()
        cursor.close()
        conn.close()
        
        # Update overall performance after domain assessment
        analyze_and_update_performance(roll_no)
        return True
        
    except psycopg2.Error as e:
        st.error(f"Error updating domain scores: {e}")
        if conn:
            conn.close()
        return False

def update_viva_score(roll_no, viva_score, viva_response):
    """Update viva score and response"""
    conn = get_db_connection()
    if conn is None:
        return False
    try:
        cursor = conn.cursor()
        cursor.execute("""
            UPDATE pre_assessment 
            SET viva_score = %s, viva_response = %s 
            WHERE roll_no = %s
        """, (viva_score, viva_response, roll_no))
        conn.commit()
        cursor.close()
        conn.close()
        
        # Update overall performance after viva
        analyze_and_update_performance(roll_no)
        return True
        
    except psycopg2.Error as e:
        st.error(f"Error updating viva score: {e}")
        if conn:
            conn.close()
        return False

def generate_course_content(domain, week_no, hours_per_day, previous_performance=None):
    """Generate course content for a specific week"""
    model = get_quiz_model()
    
    prompt = f"""Generate comprehensive course content for Week {week_no} of {domain} course.
    Daily study time: {hours_per_day} hours
    
    Structure the content with:
    1. Week {week_no} Learning Objectives
    2. Topics to Cover This Week
    3. Daily Study Plan (distribute across {hours_per_day} hours/day for 7 days)
    4. Key Concepts and Theory
    5. Practical Exercises
    6. Mini Projects (if applicable)
    7. Resources and References
    
    Make it practical and hands-on for {domain}."""
    
    if previous_performance:
        prompt += f"\n\nAdjust difficulty based on previous performance: {previous_performance}"
    
    try:
        response = model.generate_content(prompt)
        return response.text
    except Exception as e:
        st.error(f"Error generating course content: {e}")
        return f"Week {week_no} content for {domain} - Basic curriculum outline"

def save_course_content(roll_no, week_no, content):
    """Save course content to database"""
    conn = get_db_connection()
    if conn is None:
        return False
    try:
        cursor = conn.cursor()
        cursor.execute("""
            INSERT INTO course_content (roll_no, week_no, course_content)
            VALUES (%s, %s, %s)
            ON CONFLICT (roll_no, week_no) 
            DO UPDATE SET course_content = EXCLUDED.course_content
        """, (roll_no, week_no, content))
        conn.commit()
        cursor.close()
        conn.close()
        return True
    except psycopg2.Error as e:
        st.error(f"Error saving course content: {e}")
        if conn:
            conn.close()
        return False

def get_student_data(roll_no):
    """Get complete student data"""
    conn = get_db_connection()
    if conn is None:
        return None
    try:
        cursor = conn.cursor(cursor_factory=RealDictCursor)
        
        query = """
        SELECT pa.*, op.topics_excellented, op.outcome_of_course, op.student_progress
        FROM pre_assessment pa
        LEFT JOIN overall_performance op ON pa.roll_no = op.roll_no
        WHERE pa.roll_no = %s
        """
        
        cursor.execute(query, (roll_no,))
        student_data = cursor.fetchone()
        
        if student_data:
            cursor.execute("SELECT * FROM week_quiz WHERE roll_no = %s ORDER BY week_no", (roll_no,))
            week_data = cursor.fetchall()
            
            cursor.execute("SELECT * FROM course_content WHERE roll_no = %s ORDER BY week_no", (roll_no,))
            course_data = cursor.fetchall()
            
            result = dict(student_data)
            result['week_quizzes'] = [dict(row) for row in week_data]
            result['course_contents'] = [dict(row) for row in course_data]
        else:
            result = None
        
        cursor.close()
        conn.close()
        return result
    except psycopg2.Error as e:
        st.error(f"Error retrieving student data: {e}")
        if conn:
            conn.close()
        return None

def generate_viva_question(domain, cognitive_score, domain_score):
    """Generate a viva question based on domain and scores"""
    viva_model = get_viva_model()
    
    difficulty = "basic" if (cognitive_score + domain_score) / 2 < 60 else "intermediate" if (cognitive_score + domain_score) / 2 < 80 else "advanced"
    
    prompt = f"""Generate 1 viva voce question for {domain} at {difficulty} level.
    
    Format as JSON:
    {{
        "question": "The viva question about {domain}",
        "expected_points": ["point1", "point2", "point3"],
        "evaluation_criteria": "How to evaluate the answer"
    }}
    
    Make it open-ended and suitable for oral examination focusing on {domain}."""
    
    try:
        response = viva_model.generate_content(prompt)
        json_start = response.text.find('{')
        json_end = response.text.rfind('}') + 1
        json_data = response.text[json_start:json_end]
        return json.loads(json_data)
    except Exception as e:
        st.error(f"Error generating viva question: {e}")
        return {
            "question": f"Explain the key concepts and applications of {domain} in real-world scenarios.",
            "expected_points": ["Fundamental concepts", "Practical applications", "Current trends"],
            "evaluation_criteria": "Clarity of explanation, depth of knowledge, practical understanding"
        }

def generate_questions(level, topic, section_type, domain, num_questions=1):
    """Generate quiz questions based on the selected course domain"""
    quiz_model = get_quiz_model()
    
    if section_type == "cognitive":
        prompt = f"""Generate {num_questions} cognitive reasoning questions related to {domain}.
        Focus on logical thinking, problem-solving, and analytical skills applied to {domain} concepts.
        Difficulty level: {level}/5"""
    else:  # domain
        prompt = f"""Generate {num_questions} technical knowledge questions about {domain}.
        Focus on core concepts, principles, and practical applications of {domain}.
        Difficulty level: {level}/5"""
    
    prompt += f"""
    Format as JSON array:
    [{{
        "question_text": "The question about {domain}",
        "question_type": "mcq",
        "options": ["A", "B", "C", "D"],
        "correct_answer": "A",
        "explanation": "Detailed explanation"
    }}]"""
    
    try:
        response = quiz_model.generate_content(prompt)
        json_start = response.text.find('[')
        json_end = response.text.rfind(']') + 1
        json_data = response.text[json_start:json_end]
        return json.loads(json_data)
    except Exception as e:
        st.error(f"Error parsing response: {e}")
        return []
    
def update_all_student_performances():
    """Update performance analysis for all students - utility function"""
    conn = get_db_connection()
    if conn is None:
        return False
    
    try:
        cursor = conn.cursor()
        cursor.execute("SELECT roll_no FROM pre_assessment")
        students = cursor.fetchall()
        
        success_count = 0
        for student in students:
            roll_no = student[0]
            if analyze_and_update_performance(roll_no):
                success_count += 1
        
        cursor.close()
        conn.close()
        st.success(f"Updated performance analysis for {success_count} students")
        return True
        
    except psycopg2.Error as e:
        st.error(f"Error updating all performances: {e}")
        if conn:
            conn.close()
        return False


def analyze_and_update_performance(roll_no):
    """Analyze student performance and update topics_excellented"""
    conn = get_db_connection()
    if conn is None:
        return False
    
    try:
        cursor = conn.cursor(cursor_factory=RealDictCursor)
        
        # Get student data
        cursor.execute("""
            SELECT domain, cognitive_score, domain_score, viva_score 
            FROM pre_assessment WHERE roll_no = %s
        """, (roll_no,))
        student = cursor.fetchone()
        
        if not student:
            return False
        
        # Get weekly quiz performance
        cursor.execute("""
            SELECT week_no, week_quiz_score, strong_areas, weak_areas
            FROM week_quiz WHERE roll_no = %s ORDER BY week_no
        """, (roll_no,))
        weekly_data = cursor.fetchall()
        
        # Analyze performance to determine excellented topics
        excellented_topics = []
        
        # Check cognitive performance
        if student['cognitive_score'] >= 80:
            excellented_topics.append("Logical Reasoning")
            excellented_topics.append("Problem Solving")
        
        # Check domain performance
        if student['domain_score'] >= 80:
            domain = student['domain']
            if domain == "Python":
                excellented_topics.extend(["Python Fundamentals", "Programming Logic"])
            elif domain == "Data Science":
                excellented_topics.extend(["Data Analysis", "Statistical Concepts"])
            elif domain == "Machine Learning":
                excellented_topics.extend(["ML Algorithms", "Model Training"])
        
        # Check viva performance
        if student['viva_score'] >= 80:
            excellented_topics.append("Communication Skills")
            excellented_topics.append("Technical Explanation")
        
        # Check weekly performance
        for week in weekly_data:
            if week['week_quiz_score'] >= 80:
                if week['strong_areas'] and week['strong_areas'] != 'None identified':
                    excellented_topics.append(f"Week {week['week_no']}: {week['strong_areas']}")
        
        # Generate outcome based on overall performance
        avg_score = (student['cognitive_score'] + student['domain_score'] + student['viva_score']) / 3
        
        if avg_score >= 80:
            outcome = "Excellent performance - Ready for advanced topics"
            progress = "Outstanding learner with strong grasp of concepts"
        elif avg_score >= 70:
            outcome = "Good performance - Solid foundation established"  
            progress = "Good learner with areas for improvement identified"
        elif avg_score >= 60:
            outcome = "Satisfactory performance - Basic concepts understood"
            progress = "Average learner requiring additional practice"
        else:
            outcome = "Needs improvement - Requires additional support"
            progress = "Struggling learner needing focused remediation"
        
        # Update overall_performance table
        topics_str = ", ".join(set(excellented_topics)) if excellented_topics else "No topics excellented yet"
        
        cursor.execute("""
            UPDATE overall_performance 
            SET topics_excellented = %s, outcome_of_course = %s, student_progress = %s,
                last_updated = CURRENT_TIMESTAMP
            WHERE roll_no = %s
        """, (topics_str, outcome, progress, roll_no))
        
        conn.commit()
        cursor.close()
        conn.close()
        return True
        
    except psycopg2.Error as e:
        st.error(f"Error updating performance: {e}")
        if conn:
            conn.close()
        return False


def generate_weekly_quiz(domain, week_number, previous_score=None):
    """Generate weekly quiz based on domain and performance"""
    quiz_model = get_quiz_model()
    
    difficulty_adj = ""
    if previous_score is not None:
        if previous_score < 60:
            difficulty_adj = "Make questions easier to build confidence."
        elif previous_score > 80:
            difficulty_adj = "Make questions more challenging."
    
    prompt = f"""Generate 3 quiz questions for Week {week_number} of {domain} course.
    {difficulty_adj}
    
    Focus on Week {week_number} topics of {domain}.
    Format as JSON array with question_text, question_type (mcq), options, correct_answer, explanation fields.
    Make questions practical and applicable to {domain}."""
    
    try:
        response = quiz_model.generate_content(prompt)
        json_start = response.text.find('[')
        json_end = response.text.rfind(']') + 1
        json_data = response.text[json_start:json_end]
        return json.loads(json_data)
    except Exception as e:
        st.error(f"Error generating weekly quiz: {e}")
        return []

def save_week_quiz(roll_no, week_no, quiz_data):
    """Save week quiz results and update overall performance"""
    conn = get_db_connection()
    if conn is None:
        return False
    try:
        cursor = conn.cursor()
        
        cursor.execute("""
            INSERT INTO week_quiz (roll_no, week_no, week_quiz_score, week_quiz_iq, strong_areas, weak_areas, analysis)
            VALUES (%s, %s, %s, %s, %s, %s, %s)
            ON CONFLICT (roll_no, week_no) 
            DO UPDATE SET 
                week_quiz_score = EXCLUDED.week_quiz_score,
                week_quiz_iq = EXCLUDED.week_quiz_iq,
                strong_areas = EXCLUDED.strong_areas,
                weak_areas = EXCLUDED.weak_areas,
                analysis = EXCLUDED.analysis,
                date = CURRENT_TIMESTAMP
        """, (
            roll_no, week_no, quiz_data.get('score', 0), quiz_data.get('iq', 0),
            quiz_data.get('strong_areas', ''), quiz_data.get('weak_areas', ''), 
            quiz_data.get('analysis', '')
        ))
        
        conn.commit()
        cursor.close()
        conn.close()
        
        # Update overall performance after saving quiz
        analyze_and_update_performance(roll_no)
        return True
        
    except psycopg2.Error as e:
        st.error(f"Error saving week quiz: {e}")
        if conn:
            conn.close()
        return False

def check_answer(user_answer, correct_answer, question_type):
    """Check if answer is correct"""
    if question_type == "mcq":
        return user_answer == correct_answer
    return False

def calculate_iq_score(correct_answers, total_questions, difficulty_level):
    """Calculate IQ score"""
    if total_questions == 0:
        return 100
    
    accuracy = correct_answers / total_questions
    base_iq = 100
    adjusted_score = base_iq + (accuracy - 0.5) * 40
    return max(70, min(160, int(adjusted_score)))

def main():
    # Initialize session state for login
    if 'logged_in' not in st.session_state:
        st.session_state.logged_in = False
    
    # Initialize database
    if 'db_initialized' not in st.session_state:
        if create_tables() and create_login_table():
            st.session_state.db_initialized = True
        else:
            st.error("Failed to initialize database.")
            return
    
    # Check if user is logged in
    if not st.session_state.logged_in:
        login_page()
        return
    
    # Add logout button in sidebar
    with st.sidebar:
        st.write(f"**Logged in as:** {st.session_state.user_email}")
        if st.button("Logout"):
            st.session_state.logged_in = False
            st.session_state.user_email = None
            # Clear other session states
            for key in list(st.session_state.keys()):
                if key not in ['logged_in', 'user_email', 'db_initialized']:
                    del st.session_state[key]
            st.rerun()
    
    st.title("🎯 Adaptive Quiz & Course System")
    
    # Initialize session state
    if 'current_section' not in st.session_state:
        st.session_state.current_section = 1
    if 'roll_no' not in st.session_state:
        st.session_state.roll_no = ""
    
    # Initialize Section 2 & 3 adaptive quiz variables
    if 'section2_level' not in st.session_state:
        st.session_state.section2_level = 3
    if 'section3_level' not in st.session_state:
        st.session_state.section3_level = 3
    
    # Sidebar navigation
    with st.sidebar:
        st.header("Navigation")
        sections = [
            "Section 1: Background",
            "Section 2: Cognitive Test", 
            "Section 3: Domain Knowledge",
            "Section 4: Viva Voce",
            "Section 5: Course Configuration",
            "Section 6: Course Learning",
            "Section 7: Analysis"
        ]
        
        selected_section = st.selectbox("Go to section:", sections, index=st.session_state.current_section - 1)
        if st.button("Navigate"):
            st.session_state.current_section = sections.index(selected_section) + 1
            st.rerun()
    
    # Main content
    if st.session_state.current_section == 1:
        section_1()
    elif st.session_state.current_section == 2:
        section_2()
    elif st.session_state.current_section == 3:
        section_3()
    elif st.session_state.current_section == 4:
        section_4()
    elif st.session_state.current_section == 5:
        section_5()
    elif st.session_state.current_section == 6:
        section_6()
    elif st.session_state.current_section == 7:
        section_7()

def section_1():
    st.header("📋 Section 1: Background Information")
    
    with st.form("section1_form"):
        name = st.text_input("What is your name?")
        domain = st.selectbox("Select your course:", AVAILABLE_COURSES)
        knowledge_level = st.selectbox("Rate your knowledge level:", 
                                     ["Beginner", "Intermediate", "Advanced", "Expert"])
        
        if st.form_submit_button("Complete Section 1"):
            if name and domain:
                knowledge_map = {"Beginner": 1, "Intermediate": 2, "Advanced": 3, "Expert": 4}
                
                pre_assessment_data = {
                    'name': name,
                    'domain': domain,
                    'hours_per_day': 3,
                    'weeks': 4,
                    'knowledge_scale': knowledge_map.get(knowledge_level, 2)
                }
                
                roll_no = save_pre_assessment(pre_assessment_data)
                if roll_no:
                    st.session_state.roll_no = roll_no
                    st.session_state.student_name = name
                    st.session_state.student_domain = domain
                    st.success(f"✅ Section 1 completed! Roll Number: {roll_no}")
                    st.session_state.current_section = 2
                    st.rerun()
                else:
                    st.error("Failed to save data.")
            else:
                st.error("Please fill all fields")



def section_2():
    st.header("🧠 Section 2: Cognitive Assessment")
    
    if 'section2_questions' not in st.session_state:
        st.session_state.section2_questions = []
        st.session_state.section2_current_q = 0
        st.session_state.section2_score = 0
        st.session_state.section2_completed = False
        st.session_state.section2_level = 3
        st.session_state.section2_total_questions = 0
    
    if not st.session_state.roll_no:
        st.error("Please complete Section 1 first")
        return
    
    # Show progress
    st.write(f"Current Level: {st.session_state.section2_level}/5")
    st.write(f"Questions Answered: {st.session_state.section2_current_q}/5")
    
    if st.session_state.section2_completed:
        st.success("✅ Cognitive Assessment Completed!")
        st.write(f"Final Score: {st.session_state.section2_score}/5")
        
        if st.button("Proceed to Section 3"):
            st.session_state.current_section = 3
            st.rerun()
        return
    
    # Generate new question if needed
    if st.session_state.section2_current_q < 5:
        if not st.session_state.section2_questions or len(st.session_state.section2_questions) <= st.session_state.section2_current_q:
            with st.spinner("Generating question..."):
                questions = generate_questions(
                    st.session_state.section2_level,
                    st.session_state.student_domain,
                    "cognitive",
                    st.session_state.student_domain,
                    1
                )
                if questions:
                    st.session_state.section2_questions.extend(questions)
        
        if st.session_state.section2_questions and st.session_state.section2_current_q < len(st.session_state.section2_questions):
            current_question = st.session_state.section2_questions[st.session_state.section2_current_q]
            
            st.write(f"**Question {st.session_state.section2_current_q + 1}:**")
            st.write(current_question['question_text'])
            
            with st.form(f"section2_form_{st.session_state.section2_current_q}"):
                user_answer = st.radio("Select your answer:", current_question['options'])
                
                if st.form_submit_button("Submit Answer"):
                    is_correct = check_answer(user_answer, current_question['correct_answer'], current_question['question_type'])
                    
                    if is_correct:
                        st.session_state.section2_score += 1
                        st.success("✅ Correct!")
                        # Increase difficulty if correct
                        if st.session_state.section2_level < 5:
                            st.session_state.section2_level += 1
                    else:
                        st.error(f"❌ Incorrect. Correct answer: {current_question['correct_answer']}")
                        # Decrease difficulty if wrong
                        if st.session_state.section2_level > 1:
                            st.session_state.section2_level -= 1
                    
                    st.session_state.section2_current_q += 1
                    
                    if st.session_state.section2_current_q >= 5:
                        # Calculate and save scores
                        cognitive_score = (st.session_state.section2_score / 5) * 100
                        cognitive_iq = calculate_iq_score(st.session_state.section2_score, 5, st.session_state.section2_level)
                        
                        update_cognitive_scores(st.session_state.roll_no, cognitive_score, cognitive_iq)
                        st.session_state.section2_completed = True
                    
                    st.rerun()

def section_3():
    st.header("📚 Section 3: Domain Knowledge Assessment")
    
    if 'section3_questions' not in st.session_state:
        st.session_state.section3_questions = []
        st.session_state.section3_current_q = 0
        st.session_state.section3_score = 0
        st.session_state.section3_completed = False
        st.session_state.section3_level = 3
    
    if not st.session_state.roll_no:
        st.error("Please complete previous sections first")
        return
    
    # Show progress
    st.write(f"Current Level: {st.session_state.section3_level}/5")
    st.write(f"Questions Answered: {st.session_state.section3_current_q}/5")
    
    if st.session_state.section3_completed:
        st.success("✅ Domain Knowledge Assessment Completed!")
        st.write(f"Final Score: {st.session_state.section3_score}/5")
        
        if st.button("Proceed to Section 4"):
            st.session_state.current_section = 4
            st.rerun()
        return
    
    # Generate new question if needed
    if st.session_state.section3_current_q < 5:
        if not st.session_state.section3_questions or len(st.session_state.section3_questions) <= st.session_state.section3_current_q:
            with st.spinner("Generating question..."):
                questions = generate_questions(
                    st.session_state.section3_level,
                    st.session_state.student_domain,
                    "domain",
                    st.session_state.student_domain,
                    1
                )
                if questions:
                    st.session_state.section3_questions.extend(questions)
        
        if st.session_state.section3_questions and st.session_state.section3_current_q < len(st.session_state.section3_questions):
            current_question = st.session_state.section3_questions[st.session_state.section3_current_q]
            
            st.write(f"**Question {st.session_state.section3_current_q + 1}:**")
            st.write(current_question['question_text'])
            
            with st.form(f"section3_form_{st.session_state.section3_current_q}"):
                user_answer = st.radio("Select your answer:", current_question['options'])
                
                if st.form_submit_button("Submit Answer"):
                    is_correct = check_answer(user_answer, current_question['correct_answer'], current_question['question_type'])
                    
                    if is_correct:
                        st.session_state.section3_score += 1
                        st.success("✅ Correct!")
                        # Increase difficulty if correct
                        if st.session_state.section3_level < 5:
                            st.session_state.section3_level += 1
                    else:
                        st.error(f"❌ Incorrect. Correct answer: {current_question['correct_answer']}")
                        # Decrease difficulty if wrong
                        if st.session_state.section3_level > 1:
                            st.session_state.section3_level -= 1
                    
                    st.session_state.section3_current_q += 1
                    
                    if st.session_state.section3_current_q >= 5:
                        # Calculate and save scores
                        domain_score = (st.session_state.section3_score / 5) * 100
                        domain_iq = calculate_iq_score(st.session_state.section3_score, 5, st.session_state.section3_level)
                        
                        update_domain_scores(st.session_state.roll_no, domain_score, domain_iq)
                        st.session_state.section3_completed = True
                    
                    st.rerun()

def section_4():
    st.header("🎤 Section 4: Viva Voce")
    
    if not st.session_state.roll_no:
        st.error("Please complete previous sections first")
        return
    
    if 'viva_completed' not in st.session_state:
        st.session_state.viva_completed = False
    
    if st.session_state.viva_completed:
        st.success("✅ Viva Voce Completed!")
        if st.button("Proceed to Section 5"):
            st.session_state.current_section = 5
            st.rerun()
        return
    
    # Get student data for viva
    student_data = get_student_data(st.session_state.roll_no)
    if not student_data:
        st.error("Failed to retrieve student data")
        return
    
    # Generate viva question
    if 'viva_question' not in st.session_state:
        with st.spinner("Generating viva question..."):
            viva_data = generate_viva_question(
                student_data['domain'],
                student_data['cognitive_score'],
                student_data['domain_score']
            )
            st.session_state.viva_question = viva_data
    
    st.write("**Viva Question:**")
    st.write(st.session_state.viva_question['question'])
    
    st.write("**Expected Points to Cover:**")
    for point in st.session_state.viva_question['expected_points']:
        st.write(f"• {point}")
    
    with st.form("viva_form"):
        viva_response = st.text_area("Your Answer:", height=200, placeholder="Provide your detailed answer here...")
        
        if st.form_submit_button("Submit Viva Answer"):
            if viva_response.strip():
                # Simple scoring based on response length and keywords
                viva_score = min(100, len(viva_response.split()) * 2)  # Basic scoring
                
                # Save viva response
                update_viva_score(st.session_state.roll_no, viva_score, viva_response)
                
                st.success(f"✅ Viva completed! Score: {viva_score}/100")
                st.session_state.viva_completed = True
                st.rerun()
            else:
                st.error("Please provide an answer")

def section_5():
    st.header("⚙️ Section 5: Course Configuration")
    
    if not st.session_state.roll_no:
        st.error("Please complete previous sections first")
        return
    
    if 'course_configured' not in st.session_state:
        st.session_state.course_configured = False
    
    if st.session_state.course_configured:
        st.success("✅ Course Configuration Completed!")
        if st.button("Proceed to Section 6"):
            st.session_state.current_section = 6
            st.rerun()
        return
    
    st.write("Configure your learning schedule:")
    
    with st.form("config_form"):
        hours_per_day = st.slider("Hours per day:", 1, 8, 3)
        weeks = st.slider("Number of weeks:", 2, 12, 4)
        
        if st.form_submit_button("Configure Course"):
            if update_course_config(st.session_state.roll_no, hours_per_day, weeks):
                st.session_state.hours_per_day = hours_per_day
                st.session_state.weeks = weeks
                st.session_state.course_configured = True
                st.success("✅ Course configured successfully!")
                st.rerun()
            else:
                st.error("Failed to configure course")

def section_6():
    st.header("📖 Section 6: Course Learning")
    
    if not st.session_state.roll_no:
        st.error("Please complete previous sections first")
        return
    
    # Get student data
    student_data = get_student_data(st.session_state.roll_no)
    if not student_data:
        st.error("Failed to retrieve student data")
        return
    
    current_week = student_data.get('current_week_no', 1)
    total_weeks = student_data.get('weeks', 4)
    
    st.subheader(f"Week {current_week} of {total_weeks}")
    
    # Check if content exists for current week, if not generate it
    course_content = None
    for content in student_data.get('course_contents', []):
        if content['week_no'] == current_week:
            course_content = content['course_content']
            break
    
    # Generate content if it doesn't exist
    if not course_content:
        with st.spinner(f"Generating Week {current_week} content..."):
            # Get previous week performance for content adaptation
            previous_performance = None
            if current_week > 1:
                for q in student_data.get('week_quizzes', []):
                    if q['week_no'] == current_week - 1:
                        previous_performance = q.get('analysis', '')
                        break
            
            course_content = generate_course_content(
                st.session_state.student_domain, 
                current_week, 
                student_data.get('hours_per_day', 3),
                previous_performance
            )
            
            # Save the generated content
            if save_course_content(st.session_state.roll_no, current_week, course_content):
                st.success(f"Week {current_week} content generated successfully!")
            else:
                st.error("Failed to save course content")
    
    # Display course content
    if course_content:
        st.markdown("### Course Content")
        st.markdown(course_content)
    else:
        st.warning("No content available for this week")
    
    # Weekly Quiz Section
    st.markdown("---")
    st.subheader(f"Week {current_week} Quiz")
    
    # Check if quiz already taken
    quiz_taken = any(q['week_no'] == current_week for q in student_data.get('week_quizzes', []))
    
    if not quiz_taken:
        if 'weekly_quiz' not in st.session_state or st.session_state.get('current_quiz_week') != current_week:
            # Reset quiz state for new week
            st.session_state.weekly_quiz = []
            st.session_state.weekly_quiz_idx = 0
            st.session_state.weekly_quiz_score = 0
            st.session_state.current_quiz_week = current_week
        
        if not st.session_state.weekly_quiz:
            with st.spinner("Generating weekly quiz..."):
                # Get previous week performance if available
                prev_score = None
                if current_week > 1:
                    for q in student_data.get('week_quizzes', []):
                        if q['week_no'] == current_week - 1:
                            prev_score = q.get('week_quiz_score', 0)
                            break
                
                quiz_questions = generate_weekly_quiz(
                    st.session_state.student_domain, 
                    current_week, 
                    prev_score
                )
                st.session_state.weekly_quiz = quiz_questions
        
        # Display quiz
        if st.session_state.weekly_quiz:
            current_q_idx = st.session_state.weekly_quiz_idx
            
            if current_q_idx < len(st.session_state.weekly_quiz):
                question = st.session_state.weekly_quiz[current_q_idx]
                
                st.write(f"**Question {current_q_idx + 1}:**")
                st.write(question.get('question_text', ''))
                
                options = question.get('options', [])
                user_answer = st.radio("Choose your answer:", options, key=f"weekly_q{current_week}_{current_q_idx}")
                
                if st.button("Submit Answer", key=f"weekly_submit{current_week}_{current_q_idx}"):
                    correct = check_answer(user_answer, question.get('correct_answer'), question.get('question_type'))
                    if correct:
                        st.session_state.weekly_quiz_score += 1
                        st.success("Correct!")
                    else:
                        st.error(f"Incorrect. The correct answer is: {question.get('correct_answer')}")
                    
                    st.session_state.weekly_quiz_idx += 1
                    st.rerun()
            else:
                # Quiz completed
                total_q = len(st.session_state.weekly_quiz)
                quiz_score = (st.session_state.weekly_quiz_score / total_q) * 100
                quiz_iq = calculate_iq_score(st.session_state.weekly_quiz_score, total_q, 3)
                
                st.success(f"✅ Week {current_week} Quiz Complete!")
                st.write(f"Score: {st.session_state.weekly_quiz_score}/{total_q} ({quiz_score:.1f}%)")
                
                # Analyze performance
                if quiz_score >= 80:
                    strong_areas = f"Week {current_week} topics"
                    weak_areas = "None identified"
                    analysis = "Excellent performance"
                elif quiz_score >= 60:
                    strong_areas = f"Most Week {current_week} topics"
                    weak_areas = "Minor gaps identified"
                    analysis = "Good performance with room for improvement"
                else:
                    strong_areas = "Basic concepts"
                    weak_areas = f"Week {current_week} advanced topics"
                    analysis = "Needs more practice"
                
                # Save quiz results
                quiz_data = {
                    'score': quiz_score,
                    'iq': quiz_iq,
                    'strong_areas': strong_areas,
                    'weak_areas': weak_areas,
                    'analysis': analysis
                }
                
                if save_week_quiz(st.session_state.roll_no, current_week, quiz_data):
                    st.write(f"**Analysis:** {analysis}")
                    
                    # Move to next week or complete course
                    if current_week < total_weeks:
                        if st.button("Proceed to Next Week"):
                            # Update current week in database
                            next_week = current_week + 1
                            if update_current_week(st.session_state.roll_no, next_week):
                                # Clear quiz session state for next week
                                for key in ['weekly_quiz', 'weekly_quiz_idx', 'weekly_quiz_score', 'current_quiz_week']:
                                    if key in st.session_state:
                                        del st.session_state[key]
                                
                                st.success(f"Moving to Week {next_week}")
                                st.rerun()
                            else:
                                st.error("Failed to update week progress")
                    else:
                        st.success("🎉 Course Complete!")
                        if st.button("View Final Analysis"):
                            st.session_state.current_section = 7
                            st.rerun()
                else:
                    st.error("Failed to save quiz results")
    else:
        st.info(f"Week {current_week} quiz already completed")
        
        # Show completed quiz details
        for quiz in student_data.get('week_quizzes', []):
            if quiz['week_no'] == current_week:
                st.write(f"**Score:** {quiz.get('week_quiz_score', 0):.1f}%")
                st.write(f"**Analysis:** {quiz.get('analysis', 'N/A')}")
                break
        
        # Show option to move to next week or analysis
        if current_week < total_weeks:
            if st.button("Continue to Next Week"):
                next_week = current_week + 1
                if update_current_week(st.session_state.roll_no, next_week):
                    # Clear any existing quiz state
                    for key in ['weekly_quiz', 'weekly_quiz_idx', 'weekly_quiz_score', 'current_quiz_week']:
                        if key in st.session_state:
                            del st.session_state[key]
                    st.rerun()
                else:
                    st.error("Failed to update week progress")
        else:
            if st.button("View Final Analysis"):
                st.session_state.current_section = 7
                st.rerun()

def section_7():
    st.header("📊 Section 7: Performance Analysis")
    
    if not st.session_state.roll_no:
        st.error("Please complete previous sections first")
        return
    
    student_data = get_student_data(st.session_state.roll_no)
    if not student_data:
        st.error("Failed to retrieve student data")
        return
    
    # Trigger performance analysis update
    analyze_and_update_performance(st.session_state.roll_no)
    
    # Refresh data after analysis
    student_data = get_student_data(st.session_state.roll_no)
    
    # Create attractive dashboard
    st.markdown("### 🎯 Your Learning Journey Dashboard")
    
    # Main metrics
    col1, col2, col3, col4 = st.columns(4)
    
    with col1:
        st.metric(
            label="🧠 Cognitive Score",
            value=f"{student_data.get('cognitive_score', 0):.1f}%",
            delta=f"IQ: {student_data.get('cognitive_iq', 100)}"
        )
    
    with col2:
        st.metric(
            label="📚 Domain Score", 
            value=f"{student_data.get('domain_score', 0):.1f}%",
            delta=f"IQ: {student_data.get('domain_iq', 100)}"
        )
    
    with col3:
        st.metric(
            label="🎤 Viva Score",
            value=f"{student_data.get('viva_score', 0)}/100",
            delta="Oral Assessment"
        )
    
    with col4:
        overall_score = (student_data.get('cognitive_score', 0) + 
                        student_data.get('domain_score', 0) + 
                        student_data.get('viva_score', 0)) / 3
        st.metric(
            label="🌟 Overall Score",
            value=f"{overall_score:.1f}%",
            delta="Combined Performance"
        )
    
    # Topics Excellented Section - NEW
    st.markdown("### 🏆 Topics You've Mastered")
    topics_excellented = student_data.get('topics_excellented', 'No topics excellented yet')
    
    if topics_excellented and topics_excellented != 'No topics excellented yet':
        topics_list = [topic.strip() for topic in topics_excellented.split(',')]
        for topic in topics_list:
            st.success(f"✅ {topic}")
    else:
        st.info("Complete more assessments to see your mastered topics!")
    
    # Course Outcome
    st.markdown("### 📈 Course Outcome")
    outcome = student_data.get('outcome_of_course', 'Course in progress')
    st.write(f"**Status:** {outcome}")
    
    progress_desc = student_data.get('student_progress', 'Assessment in progress')
    st.write(f"**Progress:** {progress_desc}")
    
    # Progress visualization
    st.markdown("### 📈 Weekly Progress")
    
    if student_data.get('week_quizzes'):
        import pandas as pd
        
        quiz_data = []
        for quiz in student_data['week_quizzes']:
            quiz_data.append({
                'Week': f"Week {quiz['week_no']}",
                'Score': quiz['week_quiz_score'],
                'IQ': quiz['week_quiz_iq']
            })
        
        if quiz_data:
            df = pd.DataFrame(quiz_data)
            st.line_chart(df.set_index('Week'))
    
    # Performance insights
    st.markdown("### 💡 Performance Insights")
    
    # Strengths and improvements
    col1, col2 = st.columns(2)
    
    with col1:
        st.markdown("#### 🎯 Strengths")
        if student_data.get('cognitive_score', 0) >= 70:
            st.success("✅ Strong cognitive abilities")
        if student_data.get('domain_score', 0) >= 70:
            st.success("✅ Good domain knowledge")
        if student_data.get('viva_score', 0) >= 70:
            st.success("✅ Excellent communication skills")
    
    with col2:
        st.markdown("#### 🔧 Areas for Improvement")
        if student_data.get('cognitive_score', 0) < 70:
            st.warning("⚠️ Focus on logical reasoning")
        if student_data.get('domain_score', 0) < 70:
            st.warning("⚠️ Study core concepts more")
        if student_data.get('viva_score', 0) < 70:
            st.warning("⚠️ Practice verbal explanations")
    
    # Course completion status
    st.markdown("### 🏆 Course Status")
    
    current_week = student_data.get('current_week_no', 1)
    total_weeks = student_data.get('weeks', 4)
    progress = (current_week / total_weeks) * 100
    
    st.progress(progress/100)
    st.write(f"Course Progress: {progress:.1f}% ({current_week}/{total_weeks} weeks)")
    
    # Personalized recommendations
    st.markdown("### 🎯 Personalized Recommendations")
    
    recommendations = []
    
    if overall_score >= 80:
        recommendations.append("🌟 Excellent performance! Consider advanced topics.")
    elif overall_score >= 60:
        recommendations.append("👍 Good progress! Focus on weak areas.")
    else:
        recommendations.append("📚 Review fundamentals and practice more.")
    
    if student_data.get('cognitive_score', 0) > student_data.get('domain_score', 0):
        recommendations.append("💡 Strong analytical skills - dive deeper into technical concepts.")
    else:
        recommendations.append("🧠 Good domain knowledge - work on problem-solving skills.")
    
    for rec in recommendations:
        st.info(rec)
    
    # Admin function - Add button to update all student performances
    if st.button("🔄 Refresh Performance Analysis"):
        if analyze_and_update_performance(st.session_state.roll_no):
            st.success("Performance analysis updated!")
            st.rerun()
        else:
            st.error("Failed to update performance analysis")
    
    # Download report
    if st.button("📄 Download Performance Report"):
        st.success("Report generated! (Feature would download PDF in full implementation)")

if __name__ == "__main__":
    main()
