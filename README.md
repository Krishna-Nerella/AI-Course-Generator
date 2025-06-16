# 🎯 Adaptive Quiz & Course System

An AI-powered educational platform that adapts quiz difficulty, course content, and assessments based on each student's performance and learning pace. It uses **Streamlit** for the frontend, **PostgreSQL (via pgAdmin)** for data storage, and **Google Gemini AI** for dynamic quiz and content generation.

---

## 🚀 Features

- ✅ User Registration & Login with PostgreSQL
- 🎓 Personalized learning paths
- 🧠 Cognitive & Domain Knowledge Assessments
- 🎤 Viva Voce AI-based question generation
- 📚 Adaptive Course Content with weekly progress
- 📊 Performance Analysis Dashboard
- 🔐 Admin controls and performance refresh
- 📥 Data stored securely in PostgreSQL

---

## 🛠️ Technologies Used

- Python 3
- [Streamlit](https://streamlit.io/)
- [PostgreSQL](https://www.postgresql.org/) + pgAdmin
- [Google Gemini AI](https://ai.google.dev/)
- psycopg2
- pandas, json, datetime, re, os, tempfile

---

## 💾 Setup & Installation

### 1. Clone this repository
```bash
git clone https://github.com/Krishna-Nerella/AI-Course-Generator.git
cd AI-Course-Generator
```

### 2. Create a PostgreSQL Database
- Open **pgAdmin**
- Create a new database named: `AI_2`
- Note your host, username, password, and port.

### 3. Configure Database in `app.py`
Update the following section:
```python
DB_CONFIG = {
    'host': 'localhost',
    'database': 'AI_2',
    'user': 'postgres',
    'password': 'your-password',
    'port': '5432'
}
```

### 4. Add Gemini API Keys
Replace the placeholders in `app.py` with your actual Gemini API keys:
```python
GEMINI_API_KEY_QUIZ = "your-quiz-api-key"
GEMINI_API_KEY_VIVA = "your-viva-api-key"
```



### 5. Install Required Packages
```bash
pip install streamlit psycopg2-binary pandas google-generativeai
```

### 6. Run the Streamlit App
```bash
streamlit run app.py
```

---

## 📊 Dashboard Highlights

- **Real-time performance tracking**
- **Cognitive & Domain IQ scores**
- **Weekly quiz results**
- **Mastered topic list**
- **Visual progress charts**

---

## 📂 Project Structure

```
├── app.py                  # Main Streamlit app
├── requirements.txt        # List of dependencies
└── README.md               # You're here!
```

---

## 🙏 Acknowledgements

- Google Generative AI (Gemini)
- Streamlit Docs
- PostgreSQL & pgAdmin

---

## 📬 Contact

For questions or collaboration, open an issue or email: nkrishna9912@gmail.com
