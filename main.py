import streamlit as st
import os
import json
import pandas as pd
import re
import PyPDF2
import docx
import tempfile
from datetime import datetime
from io import BytesIO
import numpy as np
from tqdm import tqdm
import anthropic
from dotenv import load_dotenv
import time

# Load environment variables
load_dotenv()

# Initialize Claude API client
@st.cache_resource
def init_claude_client():
    api_key = os.getenv("ANTHROPIC_API_KEY") or st.secrets.get("ANTHROPIC_API_KEY")
    if not api_key:
        st.error("Please set your ANTHROPIC_API_KEY in the environment variables or Streamlit secrets")
        st.stop()
    return anthropic.Anthropic(api_key=api_key)

# Initialize session state
def init_session_state():
    """Initialize session state variables"""
    default_values = {
        'successful_resumes': [],
        'failed_resumes': [],
        'candidate_df': None,
        'shortlisted_df': None,
        'job_requirements': None,
        'logs': [],
        'current_job_title': "job_position",
        'total_files': 0,
        'successful_count': 0,
        'failed_count': 0,
        'top_candidates': [],
        'weights': {
            "experience": 0.30,
            "skills": 0.40,
            "education": 0.20,
            "certification": 0.10
        }
    }
    
    for key, value in default_values.items():
        if key not in st.session_state:
            st.session_state[key] = value

# Text extraction functions
def extract_text_from_pdf(pdf_file):
    """Extract text from PDF file"""
    text = ""
    try:
        pdf_reader = PyPDF2.PdfReader(pdf_file)
        for page_num in range(len(pdf_reader.pages)):
            page = pdf_reader.pages[page_num]
            page_text = page.extract_text()
            if page_text:
                text += page_text + "\n"
    except Exception as e:
        st.error(f"PDF extraction failed: {str(e)}")
    return text

def extract_text_from_docx(docx_file):
    """Extract text from DOCX file"""
    text = ""
    try:
        doc = docx.Document(docx_file)
        for paragraph in doc.paragraphs:
            text += paragraph.text + "\n"
        
        for table in doc.tables:
            for row in table.rows:
                for cell in row.cells:
                    text += cell.text + " "
                text += "\n"
    except Exception as e:
        st.error(f"DOCX extraction failed: {str(e)}")
    return text

def extract_text_from_file(uploaded_file):
    """Extract text based on file type"""
    file_ext = uploaded_file.name.lower().split('.')[-1]
    
    if file_ext == "pdf":
        return extract_text_from_pdf(uploaded_file)
    elif file_ext in ["docx", "doc"]:
        return extract_text_from_docx(uploaded_file)
    else:
        st.error(f"Unsupported file type: {file_ext}")
        return ""

# Claude API functions
def get_resume_extraction_prompt(resume_text, filename_experience=None):
    """Generate prompt for resume information extraction"""
    experience_instruction = ""
    if filename_experience:
        experience_instruction = f"""
    IMPORTANT - The total work experience for this candidate is "{filename_experience}". 
    Use this exact value for the "Total_Experience" field in your JSON output.
    """
    
    prompt = f"""You are a precise resume information extractor for an Applicant Tracking System. Extract information exactly as it appears in the resume and format it as JSON.{experience_instruction}

Your response must be ONLY a valid JSON object with this exact structure:

{{
    "Name": "", 
    "Phone": "",  
    "Email": "",    
    "Location": "", 
    "Links": [],    
    "Profile_Summary": "", 
    "Skills": [],   
    "Education": [
        {{
            "Degree": "",      
            "Institution": "", 
            "Year": "",        
            "Score": "",       
            "Type": ""         
        }}
    ],
    "Certifications": [], 
    "Total_Experience": "", 
    "Work_Experience": [
        {{
            "Position": "",     
            "Company": "",      
            "Location": "",     
            "Duration": "",     
            "Start_Date": "",   
            "End_Date": "",     
            "Responsibilities": [] 
        }}
    ],
    "Projects": [
        {{
            "Title": "",        
            "Duration": "",     
            "Description": "",  
            "Technologies": []  
        }}
    ],
    "Additional_Information": "" 
}}

EXTRACTION RULES:
1. Extract information exactly as stated in the resume
2. For dates, use format shown in resume. Use "Present" for current positions
3. For "Phone", extract ONLY phone numbers without labels
4. For "Email", extract only email addresses
5. For education, classify as "Degree", "12th", or "10th" in the "Type" field
6. Extract all skills mentioned, keeping original terminology
7. For responsibilities, create an array of distinct bullet points
8. Use empty strings for missing text fields and empty arrays for missing list fields
9. Return ONLY the JSON object, no additional text

Resume Text:
{resume_text}"""
    
    return prompt

def get_candidate_scoring_prompt(job_description, candidate_data, weights, additional_preferences=""):
    """Generate prompt for candidate scoring against job description"""
    
    # Format candidate data
    candidate_skills = ", ".join(candidate_data.get("Skills", [])) if candidate_data.get("Skills") else "None listed"
    candidate_experience = candidate_data.get("Total_Experience", "Not specified")
    
    # Format work experience
    work_experience = ""
    if candidate_data.get("Work_Experience"):
        for idx, exp in enumerate(candidate_data["Work_Experience"]):
            work_experience += f"Position {idx+1}: {exp.get('Position', 'Unknown')} at {exp.get('Company', 'Unknown')}, {exp.get('Duration', 'Duration not specified')}\n"
            if exp.get("Responsibilities"):
                work_experience += "   Key Responsibilities:\n"
                for resp in exp.get("Responsibilities")[:3]:
                    work_experience += f"   - {resp}\n"
    else:
        work_experience = "No work experience listed"
    
    # Format education
    education = ""
    if candidate_data.get("Education"):
        for idx, edu in enumerate(candidate_data["Education"]):
            education += f"Education {idx+1}: {edu.get('Degree', 'Unknown')} from {edu.get('Institution', 'Unknown')}, {edu.get('Year', 'Year not specified')}\n"
    else:
        education = "No education listed"
    
    # Format certifications
    certifications = ""
    if candidate_data.get("Certifications") and candidate_data.get("Certifications"):
        if isinstance(candidate_data.get("Certifications"), list):
            certifications = ", ".join([str(cert) for cert in candidate_data.get("Certifications")])
        else:
            certifications = str(candidate_data.get("Certifications"))
    else:
        certifications = "None listed"
    
    additional_criteria = ""
    if additional_preferences.strip():
        additional_criteria = f"""
ADDITIONAL HIRING PREFERENCES:
{additional_preferences}

Please consider these preferences when scoring the candidate.
"""
    
    prompt = f"""You are an expert HR recruiter evaluating how well a candidate matches a job description. 

SCORING WEIGHTS:
- Experience: {weights['experience'] * 100}%
- Skills: {weights['skills'] * 100}%
- Education: {weights['education'] * 100}%
- Certifications: {weights['certification'] * 100}%

JOB DESCRIPTION:
{job_description}

{additional_criteria}

CANDIDATE INFORMATION:
Name: {candidate_data.get('Name', 'Not provided')}
Total Experience: {candidate_experience}
Skills: {candidate_skills}
Work Experience: {work_experience}
Education: {education}
Certifications: {certifications}
Profile Summary: {candidate_data.get('Profile_Summary', 'Not provided')}

Analyze the candidate and return ONLY a JSON object with this structure:

{{
    "candidate_match": {{
        "name": "Candidate name",
        "match_details": {{
            "experience": {{
                "score": 85,
                "details": "Detailed explanation of experience match"
            }},
            "skills": {{
                "score": 70,
                "matching_skills": ["skill1", "skill2"],
                "missing_skills": ["skill3", "skill4"],
                "details": "Detailed explanation of skills match"
            }},
            "education": {{
                "score": 90,
                "details": "Detailed explanation of education match"
            }},
            "certifications": {{
                "score": 60,
                "details": "Detailed explanation of certifications match"
            }}
        }},
        "overall_score": 78.5,
        "explanation": "Detailed explanation of why this candidate is/isn't a good match",
        "key_strengths": ["strength1", "strength2", "strength3"],
        "key_gaps": ["gap1", "gap2"],
        "recommendation": "HIGHLY_RECOMMENDED/RECOMMENDED/CONSIDER/NOT_RECOMMENDED"
    }}
}}

Score each category from 0-100 based on relevance and quality of match. Be specific and detailed in explanations."""
    
    return prompt

def call_claude_api(client, prompt, max_tokens=3000):
    """Call Claude API with error handling"""
    try:
        response = client.messages.create(
            model=os.getenv("CLAUDE_MODEL", "claude-3-5-sonnet-20241022"),
            max_tokens=max_tokens,
            messages=[
                {"role": "user", "content": prompt}
            ]
        )
        return response.content[0].text
    except Exception as e:
        st.error(f"Claude API error: {str(e)}")
        return None

def parse_json_response(response_text):
    """Parse JSON from Claude response with error handling"""
    try:
        # Try to parse directly first
        return json.loads(response_text)
    except json.JSONDecodeError:
        # Try to extract JSON from response if it has extra text
        try:
            # Look for JSON block
            json_match = re.search(r'\{.*\}', response_text, re.DOTALL)
            if json_match:
                return json.loads(json_match.group())
        except:
            pass
        
        # Return fallback structure
        return {
            "Name": "Unknown",
            "Phone": "",
            "Email": "",
            "Location": "",
            "Links": [],
            "Profile_Summary": "",
            "Skills": [],
            "Education": [],
            "Certifications": [],
            "Total_Experience": "",
            "Work_Experience": [],
            "Projects": [],
            "Additional_Information": ""
        }

def process_resume_batch(uploaded_files, client):
    """Process uploaded resumes in batches"""
    successful_resumes = []
    failed_resumes = []
    
    # Create progress bar
    progress_bar = st.progress(0)
    status_text = st.empty()
    
    for i, uploaded_file in enumerate(uploaded_files):
        status_text.text(f"Extracting data from {uploaded_file.name}...")
        progress_bar.progress((i + 1) / len(uploaded_files))
        
        try:
            # Extract text from file
            text = extract_text_from_file(uploaded_file)
            if not text.strip():
                failed_resumes.append(uploaded_file.name)
                continue
            
            # Extract experience from filename if available
            experience = extract_experience_from_filename(uploaded_file.name)
            
            # Generate prompt
            prompt = get_resume_extraction_prompt(text, experience)
            
            # Call Claude API
            response = call_claude_api(client, prompt)
            if not response:
                failed_resumes.append(uploaded_file.name)
                continue
            
            # Parse JSON response
            candidate_data = parse_json_response(response)
            
            # Print to terminal for debugging
            print(f"\n=== EXTRACTED RESUME DATA FOR {uploaded_file.name} ===")
            print(json.dumps(candidate_data, indent=2))
            print("=" * 60)
            
            # Add metadata
            candidate_data["Source_File"] = uploaded_file.name
            candidate_data["Extraction_Date"] = datetime.now().strftime("%Y-%m-%d")
            
            successful_resumes.append(candidate_data)
            
        except Exception as e:
            st.error(f"Error processing {uploaded_file.name}: {str(e)}")
            failed_resumes.append(uploaded_file.name)
    
    status_text.text("Data extraction completed!")
    return successful_resumes, failed_resumes

def extract_experience_from_filename(filename):
    """Extract experience from filename pattern like [2y_6m]"""
    exp_pattern = r'\[(\d+)y_(\d+)m\]'
    match = re.search(exp_pattern, filename)
    
    if match:
        years = int(match.group(1))
        months = int(match.group(2))
        
        if years == 0 and months == 0:
            return "No Experience"
        elif years == 0:
            return f"{months} months"
        elif months == 0:
            return f"{years} years"
        else:
            return f"{years} years and {months} months"
    
    return None

def score_candidates_in_batches(candidates, job_description, client, weights, additional_preferences="", batch_size=10):
    """Score candidates in batches against job description"""
    scored_candidates = []
    
    # Create batches
    batches = [candidates[i:i + batch_size] for i in range(0, len(candidates), batch_size)]
    
    total_batches = len(batches)
    batch_progress = st.progress(0)
    batch_status = st.empty()
    
    for batch_idx, batch in enumerate(batches):
        batch_status.text(f"Analyzing batch {batch_idx + 1} of {total_batches} against job requirements...")
        batch_progress.progress((batch_idx + 1) / total_batches)
        
        for candidate in batch:
            try:
                prompt = get_candidate_scoring_prompt(job_description, candidate, weights, additional_preferences)
                response = call_claude_api(client, prompt, max_tokens=2000)
                
                if response:
                    match_data = parse_json_response(response)
                    
                    if "candidate_match" in match_data:
                        candidate_match = match_data["candidate_match"]
                        
                        candidate_record = {
                            'candidate_data': candidate,
                            'match_details': candidate_match.get('match_details', {}),
                            'overall_score': candidate_match.get('overall_score', 0),
                            'explanation': candidate_match.get('explanation', "No explanation provided"),
                            'key_strengths': candidate_match.get('key_strengths', []),
                            'key_gaps': candidate_match.get('key_gaps', []),
                            'recommendation': candidate_match.get('recommendation', 'CONSIDER')
                        }
                        
                        scored_candidates.append(candidate_record)
                    else:
                        # Fallback scoring
                        scored_candidates.append(create_fallback_score(candidate))
                else:
                    scored_candidates.append(create_fallback_score(candidate))
                    
            except Exception as e:
                st.error(f"Error scoring candidate {candidate.get('Name', 'Unknown')}: {str(e)}")
                scored_candidates.append(create_fallback_score(candidate))
        
        # Small delay between batches to avoid rate limiting
        time.sleep(1)
    
    batch_status.text("Candidate scoring completed!")
    
    # Sort by score
    scored_candidates.sort(key=lambda x: x['overall_score'], reverse=True)
    return scored_candidates

def create_fallback_score(candidate):
    """Create fallback score when API fails"""
    return {
        'candidate_data': candidate,
        'match_details': {
            'experience': {'score': 50, 'details': 'Could not evaluate'},
            'skills': {'score': 50, 'details': 'Could not evaluate'},
            'education': {'score': 50, 'details': 'Could not evaluate'},
            'certifications': {'score': 50, 'details': 'Could not evaluate'}
        },
        'overall_score': 50,
        'explanation': "Could not fully evaluate due to processing issues",
        'key_strengths': ["Unable to determine"],
        'key_gaps': ["Unable to determine"],
        'recommendation': 'CONSIDER'
    }

def convert_to_dataframe(resumes_data):
    """Convert resume data to DataFrame"""
    if not resumes_data:
        return None
    
    # Create DataFrame
    df = pd.DataFrame(resumes_data)
    
    # Process nested fields
    def extract_education(edu_list):
        if not edu_list or not isinstance(edu_list, list):
            return ""
        return "; ".join([f"{e.get('Degree', '')} from {e.get('Institution', '')} ({e.get('Year', '')})" for e in edu_list if e])
    
    def extract_work_exp(exp_list):
        if not exp_list or not isinstance(exp_list, list):
            return ""
        return "; ".join([f"{e.get('Position', '')} at {e.get('Company', '')} ({e.get('Duration', '')})" for e in exp_list if e])
    
    def extract_skills(skills_list):
        if not skills_list or not isinstance(skills_list, list):
            return ""
        return ", ".join([str(skill) for skill in skills_list])
    
    # Apply processing
    if "Education" in df.columns:
        df["Education_Summary"] = df["Education"].apply(extract_education)
        df = df.drop(columns=["Education"])
        
    if "Work_Experience" in df.columns:
        df["Work_Summary"] = df["Work_Experience"].apply(extract_work_exp)
        df = df.drop(columns=["Work_Experience"])
        
    if "Skills" in df.columns:
        df["Skills_List"] = df["Skills"].apply(extract_skills)
        df = df.drop(columns=["Skills"])
    
    # Convert any remaining list columns to strings
    for col in df.columns:
        if df[col].dtype == 'object':
            df[col] = df[col].apply(
                lambda x: ", ".join(x) if isinstance(x, list) else str(x) if x is not None else ""
            )
    
    return df

def create_excel_report(scored_candidates, job_description):
    """Create comprehensive Excel report"""
    output = BytesIO()
    
    with pd.ExcelWriter(output, engine='openpyxl') as writer:
        # Main candidates sheet
        main_data = []
        for idx, candidate in enumerate(scored_candidates):
            candidate_info = candidate['candidate_data']
            match_details = candidate['match_details']
            
            row = {
                "Rank": idx + 1,
                "Name": candidate_info.get("Name", "Unknown"),
                "Overall_Score": f"{candidate.get('overall_score', 0):.1f}%",
                "Recommendation": candidate.get('recommendation', 'CONSIDER'),
                "Experience_Score": f"{match_details.get('experience', {}).get('score', 0):.1f}%",
                "Skills_Score": f"{match_details.get('skills', {}).get('score', 0):.1f}%",
                "Education_Score": f"{match_details.get('education', {}).get('score', 0):.1f}%",
                "Certification_Score": f"{match_details.get('certifications', {}).get('score', 0):.1f}%",
                "Total_Experience": candidate_info.get("Total_Experience", "Not specified"),
                "Phone": candidate_info.get("Phone", ""),
                "Email": candidate_info.get("Email", ""),
                "Location": candidate_info.get("Location", ""),
                "Skills": ", ".join(candidate_info.get("Skills", [])),
                "Matching_Skills": ", ".join(match_details.get('skills', {}).get('matching_skills', [])),
                "Missing_Skills": ", ".join(match_details.get('skills', {}).get('missing_skills', [])),
                "Key_Strengths": ", ".join(candidate.get('key_strengths', [])),
                "Key_Gaps": ", ".join(candidate.get('key_gaps', [])),
                "Explanation": candidate.get('explanation', ''),
                "Resume_File": candidate_info.get("Source_File", "")
            }
            main_data.append(row)
        
        main_df = pd.DataFrame(main_data)
        main_df.to_excel(writer, sheet_name='All_Candidates', index=False)
        
        # Top 10 candidates sheet
        top_10 = main_df.head(10)
        top_10.to_excel(writer, sheet_name='Top_10_Candidates', index=False)
        
        # Job description sheet
        job_data = [
            {"Field": "Job Description", "Content": job_description},
            {"Field": "Generated On", "Content": datetime.now().strftime("%Y-%m-%d %H:%M:%S")},
            {"Field": "Total Candidates", "Content": len(scored_candidates)},
            {"Field": "Highly Recommended", "Content": len([c for c in scored_candidates if c.get('recommendation') == 'HIGHLY_RECOMMENDED'])},
            {"Field": "Recommended", "Content": len([c for c in scored_candidates if c.get('recommendation') == 'RECOMMENDED'])},
        ]
        job_df = pd.DataFrame(job_data)
        job_df.to_excel(writer, sheet_name='Job_Info', index=False)
    
    return output.getvalue()

# Streamlit UI
def main():
    st.set_page_config(
        page_title="Resume Shortlisting Tool",
        page_icon="🎯",
        layout="wide"
    )
    
    # Custom CSS
    st.markdown("""
    <style>
    .main-header {
        text-align: center;
        padding: 1rem 0;
        background: linear-gradient(90deg, #667eea 0%, #764ba2 100%);
        color: white;
        border-radius: 10px;
        margin-bottom: 2rem;
    }
    
    .upload-section {
        background-color: #f8f9fa;
        padding: 1.5rem;
        border-radius: 10px;
        margin-bottom: 1rem;
        border: 1px solid #dee2e6;
    }
    
    .candidate-card {
        background: white;
        border: 1px solid #e9ecef;
        border-radius: 15px;
        padding: 1.5rem;
        margin: 1rem 0;
        box-shadow: 0 2px 10px rgba(0,0,0,0.1);
    }
    
    .top-candidate-card {
        background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
        color: white;
        border-radius: 20px;
        padding: 2rem;
        margin: 1rem 0;
        text-align: center;
        box-shadow: 0 8px 25px rgba(102, 126, 234, 0.3);
    }
    
    .rank-badge {
        background: rgba(255,255,255,0.2);
        border: 2px solid white;
        border-radius: 50%;
        width: 60px;
        height: 60px;
        display: flex;
        align-items: center;
        justify-content: center;
        margin: 0 auto 1rem auto;
        font-size: 1.5rem;
        font-weight: bold;
    }
    
    .metric-row {
        display: flex;
        justify-content: space-around;
        margin: 1rem 0;
        padding: 1rem;
        background-color: #f8f9fa;
        border-radius: 10px;
    }
    
    .metric-item {
        text-align: center;
    }
    
    .metric-value {
        font-size: 2rem;
        font-weight: bold;
        color: #667eea;
    }
    
    .metric-label {
        font-size: 0.9rem;
        color: #6c757d;
    }
    
    .score-badge {
        display: inline-block;
        padding: 0.5rem 1rem;
        border-radius: 20px;
        font-weight: bold;
        margin: 0.5rem 0;
    }
    
    .score-excellent { background-color: #d4edda; color: #155724; }
    .score-good { background-color: #cce7ff; color: #004085; }
    .score-average { background-color: #fff3cd; color: #856404; }
    .score-poor { background-color: #f8d7da; color: #721c24; }
    </style>
    """, unsafe_allow_html=True)
    
    # Main header
    st.markdown("""
    <div class="main-header">
        <h1>🎯 AI Resume Shortlisting Tool</h1>
        <p>Intelligent candidate screening powered by AI</p>
    </div>
    """, unsafe_allow_html=True)
    
    # Initialize
    init_session_state()
    client = init_claude_client()
    
    # Sidebar for configuration
    with st.sidebar:
        st.markdown("### ⚙️ Scoring Configuration")
        
        st.markdown("**Adjust importance of each criteria:**")
        experience_weight = st.slider("Experience", 0.0, 1.0, st.session_state.weights["experience"], 0.05)
        skills_weight = st.slider("Skills", 0.0, 1.0, st.session_state.weights["skills"], 0.05)
        education_weight = st.slider("Education", 0.0, 1.0, st.session_state.weights["education"], 0.05)
        certification_weight = st.slider("Certifications", 0.0, 1.0, st.session_state.weights["certification"], 0.05)
        
        # Normalize weights
        total_weight = experience_weight + skills_weight + education_weight + certification_weight
        if total_weight > 0:
            st.session_state.weights = {
                "experience": experience_weight / total_weight,
                "skills": skills_weight / total_weight,
                "education": education_weight / total_weight,
                "certification": certification_weight / total_weight
            }
        
        st.markdown("**Current Weights:**")
        for key, value in st.session_state.weights.items():
            st.write(f"• {key.title()}: {value:.1%}")
    
    # Create tabs
    tab1, tab2, tab3 = st.tabs(["📁 Upload & Process", "👥 Candidate Details", "🏆 Shortlisted Candidates"])
    
    with tab1:
        st.markdown("### 📄 Upload Resume Files")
        uploaded_files = st.file_uploader(
            "Choose PDF, DOC, or DOCX files",
            type=["pdf", "docx", "doc"],
            accept_multiple_files=True,
            help="Upload multiple resume files to process"
        )
        
        if uploaded_files:
            st.success(f"✅ {len(uploaded_files)} files uploaded")
            
            # Show file details
            file_details = []
            for file in uploaded_files:
                file_details.append({
                    "Filename": file.name,
                    "Type": file.name.split('.')[-1].upper(),
                    "Size": f"{file.size / 1024:.1f} KB"
                })
            
            st.dataframe(pd.DataFrame(file_details), use_container_width=True)
        
        st.markdown("### 📋 Job Requirements")
        
        job_title = st.text_input("Job Title", placeholder="e.g., Senior Software Engineer")
        
        job_description = st.text_area(
            "Job Description",
            height=150,
            placeholder="Paste the complete job description...",
            help="Provide detailed job description for better matching"
        )
        
        additional_preferences = st.text_area(
            "Additional Hiring Preferences (Optional)",
            height=80,
            placeholder="e.g., Prefer candidates with startup experience...",
            help="Add specific preferences beyond the job description"
        )
        
        # Process button
        if st.button("🚀 Start Processing", type="primary", use_container_width=True):
            if not uploaded_files:
                st.error("❌ Please upload at least one resume file")
            elif not job_description:
                st.error("❌ Please enter a job description")
            else:
                st.markdown("### ⚡ Processing Results")
                
                # Step 1: Extract candidate information
                st.markdown("**📊 Extracting Resume Data**")
                successful_resumes, failed_resumes = process_resume_batch(uploaded_files, client)
                
                st.session_state.successful_resumes = successful_resumes
                st.session_state.failed_resumes = failed_resumes
                st.session_state.successful_count = len(successful_resumes)
                st.session_state.failed_count = len(failed_resumes)
                
                # Show extraction results
                col1, col2, col3 = st.columns(3)
                col1.metric("Total Files", len(uploaded_files))
                col2.metric("✅ Processed", len(successful_resumes))
                col3.metric("❌ Failed", len(failed_resumes))
                
                if successful_resumes:
                    # Step 2: Score candidates
                    st.markdown("**🎯 Scoring Candidates**")
                    scored_candidates = score_candidates_in_batches(
                        successful_resumes, 
                        job_description, 
                        client, 
                        st.session_state.weights,
                        additional_preferences
                    )
                    
                    st.session_state.top_candidates = scored_candidates
                    st.session_state.current_job_title = job_title or "Position"
                    
                    # Show scoring results
                    if scored_candidates:
                        highly_recommended = len([c for c in scored_candidates if c.get('recommendation') == 'HIGHLY_RECOMMENDED'])
                        recommended = len([c for c in scored_candidates if c.get('recommendation') == 'RECOMMENDED'])
                        avg_score = np.mean([c['overall_score'] for c in scored_candidates])
                        
                        col1, col2, col3 = st.columns(3)
                        col1.metric("🌟 Highly Recommended", highly_recommended)
                        col2.metric("👍 Recommended", recommended)
                        col3.metric("📊 Average Score", f"{avg_score:.1f}%")
                        
                        st.success("✅ Processing completed successfully!")
                        st.info("📋 Check the 'Candidate Details' and 'Shortlisted Candidates' tabs for results")
                    else:
                        st.error("❌ No candidates could be scored. Please check your files and try again.")
                else:
                    st.error("❌ No resumes were successfully processed. Please check your files and try again.")
    
    with tab2:
        st.markdown("### 👥 All Extracted Candidates")
        
        if st.session_state.successful_resumes:
            # Create and display candidate DataFrame
            candidate_df = convert_to_dataframe(st.session_state.successful_resumes)
            st.session_state.candidate_df = candidate_df
            
            if candidate_df is not None:
                st.dataframe(candidate_df, use_container_width=True)
                
                # Download buttons
                col1, col2 = st.columns(2)
                
                with col1:
                    # Download as Excel
                    excel_buffer = BytesIO()
                    with pd.ExcelWriter(excel_buffer, engine='openpyxl') as writer:
                        candidate_df.to_excel(writer, sheet_name='Candidates', index=False)
                    
                    st.download_button(
                        "📊 Download Excel",
                        data=excel_buffer.getvalue(),
                        file_name=f"candidates_{datetime.now().strftime('%Y%m%d_%H%M%S')}.xlsx",
                        mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                        use_container_width=True
                    )
                
                with col2:
                    # Download as JSON
                    json_data = json.dumps(st.session_state.successful_resumes, indent=2)
                    st.download_button(
                        "📄 Download JSON",
                        data=json_data,
                        file_name=f"candidates_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json",
                        mime="application/json",
                        use_container_width=True
                    )
        else:
            st.info("📝 No candidate data available. Please process some resumes first.")
    
    with tab3:
        st.markdown("### 🏆 Top 5 Candidates")
        
        if st.session_state.top_candidates:
            top_5 = st.session_state.top_candidates[:5]
            
            # Display top 5 candidates
            for idx, candidate in enumerate(top_5):
                candidate_info = candidate['candidate_data']
                score = candidate['overall_score']
                match_details = candidate['match_details']
                
                # Determine score class
                if score >= 85:
                    score_class = "score-excellent"
                elif score >= 70:
                    score_class = "score-good"
                elif score >= 55:
                    score_class = "score-average"
                else:
                    score_class = "score-poor"
                
                st.markdown(f"""
                <div class="top-candidate-card">
                    <div class="rank-badge">#{idx+1}</div>
                    <h3>{candidate_info.get('Name', 'Unknown')}</h3>
                    <div class="score-badge {score_class}" style="background: rgba(255,255,255,0.2); color: white;">
                        {score:.1f}% Match
                    </div>
                    <p><strong>📧 Email:</strong> {candidate_info.get('Email', 'N/A')}</p>
                    <p><strong>📱 Phone:</strong> {candidate_info.get('Phone', 'N/A')}</p>
                    <p><strong>💼 Experience:</strong> {candidate_info.get('Total_Experience', 'Not specified')}</p>
                    <p><strong>🎯 Recommendation:</strong> {candidate.get('recommendation', 'CONSIDER')}</p>
                </div>
                """, unsafe_allow_html=True)
                
                # Detailed explanation
                with st.expander(f"📝 Detailed Analysis - {candidate_info.get('Name', 'Unknown')}"):
                    col1, col2 = st.columns(2)
                    
                    with col1:
                        st.markdown("**💡 Why this candidate:**")
                        st.write(candidate.get('explanation', 'No explanation provided'))
                        
                        st.markdown("**✅ Key Strengths:**")
                        for strength in candidate.get('key_strengths', ['Not specified']):
                            st.write(f"• {strength}")
                        
                        st.markdown("**📈 Areas for Development:**")
                        for gap in candidate.get('key_gaps', ['None identified']):
                            st.write(f"• {gap}")
                    
                    with col2:
                        st.markdown("**📊 Score Breakdown:**")
                        
                        # Create score metrics
                        exp_score = match_details.get('experience', {}).get('score', 0)
                        skills_score = match_details.get('skills', {}).get('score', 0)
                        edu_score = match_details.get('education', {}).get('score', 0)
                        cert_score = match_details.get('certifications', {}).get('score', 0)
                        
                        st.metric("Experience", f"{exp_score:.1f}%")
                        st.metric("Skills", f"{skills_score:.1f}%")
                        st.metric("Education", f"{edu_score:.1f}%")
                        st.metric("Certifications", f"{cert_score:.1f}%")
                        
                        # Skills matching details
                        matching_skills = match_details.get('skills', {}).get('matching_skills', [])
                        if matching_skills:
                            st.markdown("**✅ Matching Skills:**")
                            for skill in matching_skills[:5]:
                                st.write(f"• {skill}")
            
            st.markdown("---")
            
            # All shortlisted candidates
            st.markdown("### 📋 All Shortlisted Candidates")
            
            # Create summary table
            summary_data = []
            for idx, candidate in enumerate(st.session_state.top_candidates):
                candidate_info = candidate['candidate_data']
                summary_data.append({
                    "Rank": idx + 1,
                    "Name": candidate_info.get("Name", "Unknown"),
                    "Score": f"{candidate.get('overall_score', 0):.1f}%",
                    "Recommendation": candidate.get('recommendation', 'CONSIDER'),
                    "Experience": candidate_info.get("Total_Experience", "Not specified"),
                    "Email": candidate_info.get("Email", ""),
                    "Phone": candidate_info.get("Phone", ""),
                    "Resume File": candidate_info.get("Source_File", "")
                })
            
            summary_df = pd.DataFrame(summary_data)
            st.dataframe(summary_df, use_container_width=True)
            
            # Download options
            st.markdown("### 📥 Download Reports")
            
            col1, col2, col3 = st.columns(3)
            
            with col1:
                # Download all candidates CSV
                csv_data = summary_df.to_csv(index=False).encode('utf-8')
                st.download_button(
                    "📊 Download All Candidates CSV",
                    data=csv_data,
                    file_name=f"shortlisted_candidates_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv",
                    mime="text/csv",
                    use_container_width=True
                )
            
            with col2:
                # Download top 5 CSV
                top_5_csv = summary_df.head(5).to_csv(index=False).encode('utf-8')
                st.download_button(
                    "🏆 Download Top 5 CSV",
                    data=top_5_csv,
                    file_name=f"top_5_candidates_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv",
                    mime="text/csv",
                    use_container_width=True
                )
            
            with col3:
                # Download complete Excel report
                if 'job_description' in locals():
                    excel_data = create_excel_report(st.session_state.top_candidates, job_description)
                else:
                    excel_data = create_excel_report(st.session_state.top_candidates, "Job Description Not Available")
                
                st.download_button(
                    "📈 Download Complete Excel Report",
                    data=excel_data,
                    file_name=f"complete_report_{datetime.now().strftime('%Y%m%d_%H%M%S')}.xlsx",
                    mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                    use_container_width=True
                )
        
        else:
            st.info("🎯 No candidates have been shortlisted yet. Please process some resumes first.")

if __name__ == "__main__":
    main()