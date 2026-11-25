# Projects — Mohammed Tariq Athar Faheem

Data engineering, analytics and software projects in Python and SQL. Each folder is self-contained, with its own README, `requirements.txt` and tests.

| Project | What it shows | Stack |
|---|---|---|
| [**Retail Sales ETL Pipeline**](retail-sales-etl/) | Batch ETL from messy CSV exports into a star schema, with quarantine, run logging, automated data-quality checks and SQL analytics (window functions) | Python, pandas, SQLite, SQL |
| [**Sentiment Analysis**](sentiment-analysis/) | NLP classification of 2,000 movie reviews: text cleaning, TF-IDF, comparing Naive Bayes, Logistic Regression and SVM with cross-validation (~87% accuracy) | Python, scikit-learn, matplotlib |
| [**Smart Parking System**](smart-parking-system/) | Multi-level parking manager: best-fit slot allocation, ticketing, fee rules, reports, CLI and a one-day traffic simulation | Python (OOP), SQLite, pytest |
| [Eye Blinking Dataset](Eye%20Blinking%20Dataset.ipynb) | EDA and classification on EEG eye-state data ([OpenML 1471](https://www.openml.org/search?type=data&sort=runs&status=active&id=1471)) | Jupyter, pandas |
| [Justdial Data Cleaning](Justdial%20data%20cleaning.ipynb) | Cleaning a scraped business-listings dataset (notes below) | Jupyter, pandas |

## Quick start

```bash
git clone https://github.com/T4R1QF4H33M/Real-Time-Projects.git
cd Real-Time-Projects/<project-folder>
pip install -r requirements.txt
python -m pytest -q tests
```

---

## Justdial Dataset — Data Cleaning notes

- Deleted duplicate rows using Excel.
- Combined the "Price for Two" and "Rupees" columns into one and deleted the rupees column. Filled NaN values in this column with 00000.
- Converted the "People recently enquired" column into a column holding just the number. Filled NaN values with 0, meaning 0 people enquired.
- The column with 'Order Online', 'Menu' and NaN values had 'Order Online' as its most frequent value, so it was converted into a column showing whether online ordering was available: 'Order Online' → 'Yes'; 'Menu' and NaN → 'No'.
- Two columns had the same contact information. Deleted one, cleaned the other and replaced NaN values with 'Not Available'.
- Deleted the column whose only value was 'more'.
- Deleted the suggestions column because 70% of its values were NaN.
- Deleted the column with values like 'Clean Place' because 70% of its values were NaN.
- Combined 5 amenity columns into one.
- Cleaned the '... Years in Business' column and replaced NaN values with 'Not Available'.
- Deleted the 'Open till ...' and 'Open' columns because they added no useful information.
- Cleaned the address column.
- Cleaned the '... Ratings' column.
- Dropped the URL columns because they added no useful information.
- Cleaned the column with values like 'Trending' and imputed NaN values with 'Not Available'.
- Converted the column with the value 'This business Information is verified by Justdial.' into a boolean column.
