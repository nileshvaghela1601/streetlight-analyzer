# Streetlight Complaint Analyzer

Web application – **Drop your CSV / Excel** and instantly get:

- Most affected locations (Ward / Pincode)
- Repeating complaint detection
- Resolution time analysis
- Open vs Closed status
- Health score (RED / AMBER / GREEN)
- Downloadable Excel report

## How to Run

```bash
# 1. Go to the folder
cd streetlight_analyzer

# 2. Install dependencies
pip install -r requirements.txt

# 3. Start the web app
streamlit run app.py
```

The app will open in your browser (usually http://localhost:8501).

## Usage

1. Click **Browse files** or drag-and-drop your CSV / Excel
2. The app automatically detects columns (Citizen Mobile, Remarks, Location, Status, dates…)
3. Explore the 5 tabs:
   - 📍 Hotspots
   - 🔄 Repeating Complaints
   - ⏱️ Resolution Time
   - 📊 Status & Trends
   - 📋 Full Data
4. Download the full analysis Excel at the bottom of the last tab

## Supported File Formats

- `.csv`
- `.xlsx` / `.xls`

Works best with the standard AMC complaint export that contains columns like:
Citizen Mobile, Citizen Remarks, Location Address, Status, Registration Date Time, Action DateTime, Ward.
