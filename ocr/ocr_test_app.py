import streamlit as st
import pandas as pd
from pathlib import Path
import base64
from google.cloud import storage
import io
from dotenv import load_dotenv
import os
import base64
import ast
import json
load_dotenv("/Users/paigegiese/SYG/landproDATA_code/misc-work/.env", override=True)
os.environ['GOOGLE_APPLICATION_CREDENTIALS'] = '/Users/paigegiese/SYG/landproDATA_admin/landprodata-server-65e4697bdfe1.json'

def load_pdf_from_gcs(bucket_name, blob_name):
    client = storage.Client() 
    bucket = client.bucket(bucket_name)
    blob = bucket.blob(blob_name)
    pdf_bytes = blob.download_as_bytes()
    return pdf_bytes

def show_pdf(pdf_bytes):
    base64_pdf = base64.b64encode(pdf_bytes).decode('utf-8')
    pdf_display = f'<iframe src="data:application/pdf;base64,{base64_pdf}" width="100%" height="700px" type="application/pdf"></iframe>'
    st.markdown(pdf_display, unsafe_allow_html=True)

rows = pd.read_csv('/Users/paigegiese/SYG/landproDATA_code/misc-work/ocr/test_documents_successful_responses_wide.csv')[['blob_name_short','blob_name','text_answer','ocr_answer_sorted']].head(3).to_dict('records')

def sort_json_people_entities(data):
    # Sort people by full name (first + last)
    if 'people' in data:
        data['people'] = sorted(
            data['people'],
            key=lambda x: f"{x.get('first_name', '')} {x.get('last_name', '')}"
        )
    # Sort entities by 'name'
    if 'entities' in data:
        data['entities'] = sorted(
            data['entities'],
            key=lambda x: x.get('name', '')
        )
    return data

for r in rows:
    try:
        r['ocr_answer_sorted'] = sort_json_people_entities(ast.literal_eval(r['ocr_answer_sorted']))
        r['text_answer']= sort_json_people_entities(ast.literal_eval(r['text_answer']))
    except: 
        continue


criteria = [
    "Extracted all necessary and correct information (True Positive)",
    "Extracted incorrect information (False Positive)",
    "Missed necessary information (False Negative)",
    "Extracted nothing when there was nothing to extract (True Negative)",
    "Handled formatting better (Subjective/Other)",
    "Other (explain below)"
]


# --- STREAMLIT APP ---
st.markdown(
    """
    <style>
    .main {
        max-width: 95vw !important;
    }
    .block-container {
        max-width: 1800px;
        padding-left: 2rem;
        padding-right: 2rem;
    }
    </style>
    """,
    unsafe_allow_html=True,
)
st.title("OCR Output Comparison")

# Keep results in session state
if "results" not in st.session_state:
    st.session_state["results"] = []

case_idx = st.session_state.get("case_idx", 0)

if case_idx >= len(rows):
    st.success("All cases complete! Download your results below.")
    df = pd.DataFrame(st.session_state["results"])
    st.download_button("Download CSV", df.to_csv(index=False), "ocr_comparison_results.csv")
    st.stop()

case = rows[case_idx]
pathy = case["blob_name"]
pdf_bytes = load_pdf_from_gcs(os.getenv("GCS_BUCKET"), pathy) #TEST
st.download_button("Download PDF", data=pdf_bytes, file_name="document.pdf")
show_pdf(pdf_bytes)

#st.image(case["image_path"], caption="Original Image", use_column_width=True)
# st.markdown("#### DocAI Output")
# st.text_area("DocAI", case["text_answer"], height=100, disabled=True)
# st.markdown("#### Unstract Output")
# st.text_area("Unstract", case["ocr_answer_sorted"], height=100, disabled=True)

col1, col2 = st.columns([2,2])

with col1:
    st.subheader("DocAI Output")
    st.json(case["text_answer"])

with col2:
    st.subheader("Unstract Output")
    st.json(case["ocr_answer_sorted"])

with st.form("score_form"):
    col1, col2 = st.columns([2,2])
    with col1:
        st.markdown("### DocAI Feedback")
        criteria1 = st.selectbox(
            "Score for DocAI:",
            criteria,
            key="criteria1"
        )
        explain1 = ""
        if criteria1 == "Other (explain below)":
            explain1 = st.text_area("Please explain (DocAI):", key="explain1")
        else:
            explain1 = st.text_area("Additional comments (DocAI):", key="explain1a")
    with col2:
        st.markdown("### Unstract Feedback")
        criteria2 = st.selectbox(
            "Score for Unstract:",
            criteria,
            key="criteria2"
        )
        explain2 = ""
        if criteria2 == "Other (explain below)":
            explain2 = st.text_area("Please explain (Unstract):", key="explain2")
        else:
            explain2 = st.text_area("Additional comments (Unstract):", key="explain2a")

    st.markdown("---")
    winner = st.radio("Which output is better overall?", ["DocAI", "Unstract", "Tie"])

    submitted = st.form_submit_button("Submit & Next")

if submitted:
    st.session_state["results"].append({
        "blob_name": case["blob_name"],
        "text_answer": case["text_answer"],
        "ocr_answer_sorted": case["ocr_answer_sorted"],
        "criteria1": criteria1,
        "explain1": explain1,
        "criteria2": criteria2,
        "explain2": explain2,
        "winner": winner
    })
    st.session_state["case_idx"] = case_idx + 1
    st.rerun()
