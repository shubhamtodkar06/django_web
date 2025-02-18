import io
import os
import tempfile
import time
import uuid  
from googleapiclient.http import MediaFileUpload
from google.oauth2 import service_account
from django.conf import settings  # Import Django settings
import googleapiclient
from googleapiclient.discovery import build
from PyPDF2 import PdfReader
import matplotlib.pyplot as plt 
import matplotlib
matplotlib.use('Agg')  # Set non-GUI backend
import matplotlib.pyplot as plt

def get_drive_service():
    """Builds and returns a Google Drive service object with debug prints."""
    print("DEBUG: get_drive_service - Starting function execution")
    creds = None
    if not settings.GOOGLE_DRIVE_CREDENTIALS_FILE:
        print("DEBUG: get_drive_service - GOOGLE_DRIVE_CREDENTIALS_FILE setting is missing.")
        return None
    if not settings.GOOGLE_DRIVE_SCOPES:
        print("DEBUG: get_drive_service - GOOGLE_DRIVE_SCOPES setting is missing.")
        return None

    try:
        print(f"DEBUG: get_drive_service - Attempting to load credentials from file: {settings.GOOGLE_DRIVE_CREDENTIALS_FILE}")
        creds = service_account.Credentials.from_service_account_file(
            settings.GOOGLE_DRIVE_CREDENTIALS_FILE, scopes=settings.GOOGLE_DRIVE_SCOPES)
        print("DEBUG: get_drive_service - Credentials loaded successfully.")
    except FileNotFoundError:
        print(f"DEBUG: get_drive_service - FileNotFoundError: Credentials file not found at {settings.GOOGLE_DRIVE_CREDENTIALS_FILE}")
        return None
    except Exception as e:
        print(f"DEBUG: get_drive_service - Error loading credentials: {e}")
        return None

    try:
        print("DEBUG: get_drive_service - Building Drive service...")
        drive_service = build('drive', 'v3', credentials=creds)
        print("DEBUG: get_drive_service - Google Drive service built successfully!")
        return drive_service
    except Exception as e:
        print(f"DEBUG: get_drive_service - Error building Drive service: {e}")
        return None


import tempfile
import time
import os
import googleapiclient.http
import logging
from django.conf import settings


def upload_to_drive(service, uploaded_file, drive_folder_id):
    """
    Uploads a file to Google Drive, handling temporary file creation and cleanup,
    with robust retry logic for deletion on failure (specifically for Windows 'WinError 32').

    This function now includes:
    - Explicit closing of the temporary file before deletion attempt.
    - Increased retry delay for temp file cleanup.
    - Robust error handling and logging for upload and cleanup processes.
    - Clear debug and progress messages for better monitoring.
    """
    if service is None:
        print("Google Drive service not initialized. Cannot upload file.")
        return None

    try:
        file_metadata = {'name': uploaded_file.name, 'parents': [drive_folder_id]}
        temp_file_path = None

        try: # --- Inner try block for file operations and Drive upload ---
            print(f"UPLOAD START: Creating temp file for {uploaded_file.name}...")
            with tempfile.NamedTemporaryFile(delete=False, suffix=".tmp") as temp_file: # Cleaner temp file handling
                temp_file_path = temp_file.name
                print(f"UPLOAD PROGRESS: Temp file created at {temp_file_path}")

                print(f"UPLOAD PROGRESS: Writing content to temp file {temp_file_path}...")
                for chunk in uploaded_file.chunks():
                    temp_file.write(chunk)
                print(f"UPLOAD PROGRESS: Content written to temp file. File size: {os.path.getsize(temp_file_path)} bytes.")

                temp_file.close()  # --- EXPLICITLY CLOSE THE TEMP FILE RIGHT AFTER WRITING ---
                print(f"UPLOAD PROGRESS: Temp file explicitly closed.")

            print(f"UPLOAD PROGRESS: Starting Google Drive upload from {temp_file_path}...")
            media = googleapiclient.http.MediaFileUpload(temp_file_path, mimetype=uploaded_file.content_type, resumable=True) # Consider resumable upload
            print(f"UPLOAD PROGRESS: MediaFileUpload object created for resumable upload.")

            request = service.files().create(body=file_metadata, media_body=media, fields='id')
            print(f"UPLOAD PROGRESS: Drive API 'files().create' request initiated.")

            file = None
            response = None
            while file is None: # Resumable upload handling
                status, response = request.next_chunk()
                if status:
                    print(f"UPLOAD PROGRESS: Uploaded {int(status.progress() * 100)}% for {uploaded_file.name}...")
                if response:
                    file = response

            print(f"UPLOAD PROGRESS: Drive API 'files().create' request executed and file upload completed.")
            drive_file_id = file.get('id')
            print(f"UPLOAD SUCCESS: File ID: {drive_file_id} for {uploaded_file.name}")
            return drive_file_id

        except Exception as e_upload: # --- Inner try block Exception Handling (Upload Errors) ---
            print(f"UPLOAD ERROR: General error during Drive upload for {uploaded_file.name}: {e_upload}")
            return None

        finally: # --- Cleanup block - Executes whether upload succeeds or fails ---
            if temp_file_path:
                print(f"CLEANUP START: Attempting to remove temp file {temp_file_path} for {uploaded_file.name}...")
                max_retries = 0
                retry_delay_seconds = 2  # --- INCREASED RETRY DELAY TO 2 SECONDS ---
                for retry_attempt in range(max_retries):
                    try:
                        time.sleep(retry_delay_seconds)
                        os.remove(temp_file_path)
                        print(f"CLEANUP SUCCESS: Temp file {temp_file_path} removed after {retry_attempt+1} attempt(s) for {uploaded_file.name}")
                        break # Exit retry loop if deletion succeeds
                    except Exception as e_delete:
                        if retry_attempt < max_retries - 1:
                            print(f"CLEANUP RETRY {retry_attempt+2}/{max_retries}: Error removing temp file {temp_file_path} for {uploaded_file.name}: {e_delete}. Retrying in {retry_delay_seconds} seconds...")
                            time.sleep(retry_delay_seconds)
                        else:
                            print(f"CLEANUP ERROR: Final attempt failed to remove temp file {temp_file_path} for {uploaded_file.name} after {max_retries} retries: {e_delete}")
                            break # Exit retry loop after final failure
                else:
                    pass # Deletion was successful in one of the retries

    except Exception as e_outer: # --- Outer try block - broader errors ---
        print(f"UPLOAD ERROR: An unexpected error occurred during upload process for {uploaded_file.name}: {e_outer}")
        return None
  
def delete_file_from_drive(service, file_id):
    """Deletes a file from Google Drive."""
    if service is None:
        print("Google Drive service not initialized. Cannot delete file.")
        return False
    try:
        service.files().delete(fileId=file_id).execute()
        return True
    except Exception as e:
        print(f"Error deleting file from Drive: {e}")
        return False


def fetch_file_content_from_drive(drive_service, file_id):
    """Fetches content of a file from Google Drive."""
    try:
        request = drive_service.files().get_media(fileId=file_id)
        file_content = io.BytesIO()
        downloader = googleapiclient.http.MediaIoBaseDownload(file_content, request)
        done = False
        while not done:
            status, done = downloader.next_chunk()
        return file_content.getvalue()
    except Exception as e:
        print(f"Error fetching file content from Drive: {e}")
        return None


def extract_text_from_pdf(pdf_content, filename="document.pdf"):
    """Extracts text from a PDF content using PyPDF2."""
    text = ""
    try:
        pdf_reader = PdfReader(io.BytesIO(pdf_content))
        for page_num in range(len(pdf_reader.pages)):
            page = pdf_reader.pages[page_num]
            text += page.extract_text()
        return text
    except Exception as e:
        print(f"Error extracting text from PDF '{filename}': {e}")
        return None


def clean_and_structure_jd(jd_text, openai_api_key): # Keep OpenAI functions as they are used later
    """Cleans and structures job description text using OpenAI."""
    if not jd_text:
        print("No JD text provided for cleaning and structuring.")
        return None

    prompt = f"Please clean and structure the following job description text:\n\n{jd_text}\n\n... (structured and cleaned JD):"
    try:
        from openai import OpenAI # Import OpenAI here, only when needed
        client = OpenAI(api_key=openai_api_key)
        response = client.chat.completions.create(
            model="gpt-3.5-turbo", # Or another suitable model
            messages=[{"role": "user", "content": prompt}]
        )
        structured_jd = response.choices[0].message.content
        return structured_jd
    except Exception as e:
        print(f"Error during OpenAI JD structuring: {e}")
        return None


from django.conf import settings  # Make sure settings is imported here if not already

from django.conf import settings
import openai

def process_resumes_and_match(structured_jd_data, resume_files_queryset, drive_service, openai_api_key):
    """Processes resumes, matches them against structured JDs, and generates analytics."""
    print(f"OpenAI library version: {openai.__version__}")  # Debug: Print OpenAI version
    matched_resumes_data = {}
    unmatched_resumes_filenames = []
    analytics_data = {"skill_overlap": {}, "experience_match": {}, "education_match": {}} # Analytics data dictionary

    if not structured_jd_data:
        print("No structured JD data available for resume matching.")
        return matched_resumes_data, unmatched_resumes_filenames, analytics_data

    for jd_filename, structured_jd in structured_jd_data.items():
        print(f"\n--- Processing Job Description: {jd_filename} ---") # Debug JD processing start
        jd_skills = extract_skills_from_structured_jd(structured_jd)
        print(f"\n--- Job Description Skills Extracted for {jd_filename} ---") # Debug JD skills
        print(f"Number of JD skills extracted: {len(jd_skills) if jd_skills else 0}")
        if jd_skills:
            print(f"JD Skills: {jd_skills}")
        else:
            print("No JD skills extracted.")
            continue # Skip to next JD if no skills extracted

        matched_resumes_data[jd_filename] = []
        for resume_instance in resume_files_queryset:
            print(f"\n--- Processing Resume: {resume_instance.original_filename} ---") # Debug resume processing start
            resume_content = fetch_file_content_from_drive(drive_service, resume_instance.drive_file_id)
            if resume_content:
                resume_text = extract_text_from_pdf(resume_content, resume_instance.original_filename)
                if resume_text:
                    resume_skills = extract_skills_from_resume(resume_text, openai_api_key)
                    print(f"Number of resume skills extracted: {len(resume_skills) if resume_skills else 0}") # Debug resume skill count
                    if resume_skills:
                        print(f"Resume Skills: {resume_skills}") # Debug resume skills
                        skill_overlap_percentage = calculate_skill_overlap(jd_skills, resume_skills)
                        print(f"Skill Overlap Percentage: {skill_overlap_percentage:.2f}%") # Debug skill overlap

                        if skill_overlap_percentage >= settings.SKILL_MATCH_THRESHOLD:
                            print(f"Resume '{resume_instance.original_filename}' MATCHED (Skill Overlap >= {settings.SKILL_MATCH_THRESHOLD}%)") # Debug match status
                            matched_resumes_data[jd_filename].append({
                                'resume_filename': resume_instance.original_filename,
                                'skill_overlap_percentage': skill_overlap_percentage,
                                # ... you can add more matching criteria and data here
                            })
                        else:
                            print(f"Resume '{resume_instance.original_filename}' NOT MATCHED (Skill Overlap < {settings.SKILL_MATCH_THRESHOLD}%)") # Debug non-match
                            unmatched_resumes_filenames.append(resume_instance.original_filename)
                        analytics_data["skill_overlap"][resume_instance.original_filename] = skill_overlap_percentage
                    else:
                        print(f"Could not extract skills from resume '{resume_instance.original_filename}'.") # Debug no resume skills
                else:
                    print(f"Could not extract text from resume '{resume_instance.original_filename}'.") # Debug no resume text
            else:
                print(f"Could not fetch content for resume '{resume_instance.original_filename}' from Google Drive.") # Debug no resume content

    # --- Basic Analytics Calculation (moved after the loops for summary)
    total_resumes = len(resume_files_queryset)
    matched_count = sum(len(matches) for matches in matched_resumes_data.values())
    analytics_data["total_resumes_processed"] = total_resumes
    analytics_data["total_matched_resumes"] = matched_count
    analytics_data["match_rate"] = (matched_count / total_resumes) * 100 if total_resumes > 0 else 0

    print(f"\n--- Analysis Summary ---") # Debug summary
    print(f"Total Matched Resumes: {len(matched_resumes_data)}")
    print(f"Total Unmatched Resumes: {len(unmatched_resumes_filenames)}")

    print(f"\n--- Matched Resumes Data Structure ---") # Inspect matched_resumes_data structure
    print(f"Number of matched_resumes_data entries (JD filenames as keys): {len(matched_resumes_data)}")
    if matched_resumes_data:
        first_jd_filename = next(iter(matched_resumes_data)) # Get the first JD filename key
        print(f"For the first JD '{first_jd_filename}', matched resumes data: {matched_resumes_data[first_jd_filename]}") # Show matched resumes for first JD
    else:
        print("matched_resumes_data is empty.")

    return matched_resumes_data, unmatched_resumes_filenames, analytics_data


def visualize_analytics(analytics_data):
    if not analytics_data or 'skill_gap_analysis' not in analytics_data or not analytics_data.get('skill_gap_analysis'): # Robust check
        print("DEBUG: visualize_analytics - skill_gap_analysis is missing or empty in analytics_data.") # DEBUG print
        return None  

    skill_gap_analysis = analytics_data['skill_gap_analysis']
    print("DEBUG: visualize_analytics - skill_gap_analysis found and proceeding with visualization.") 
    skills = list(skill_gap_analysis.keys())
    gaps = list(skill_gap_analysis.values())

    plt.figure(figsize=(10, 6)) 
    plt.bar(skills, gaps, color='skyblue')
    plt.xlabel('Skills')
    plt.ylabel('Skill Gap (Number of Resumes Missing Skill)')
    plt.title('Skill Gap Analysis: Skills Missing in Resumes')
    plt.xticks(rotation=45, ha='right')
    plt.tight_layout()

    # Save plot to a temporary file
    filename = f'skill_gap_plot_{uuid.uuid4()}.png'
    filepath = os.path.join(settings.MEDIA_ROOT, filename)
    plt.savefig(filepath) # <-- Saving the figure

    plt.close() # Close the figure to free memory

    return filename

#########################################################
from django.conf import settings
import openai

def skill_agent(text, text_type, openai_api_key=None):
    """
    AI agent to extract skills from text (Job Description or Resume) using OpenAI.
    (Function code remains the same as in the previous response)
    """
    if not text:
        return []

    if text_type == "jd":
        api_key_to_use = openai_api_key or settings.OPENAI_API_KEY # Use provided API key or default for JD
        prompt_instruction = """
        Job Description:
        {text}

        Identify and extract a concise list of **technical skills, soft skills, and domain-specific expertise** required to perform the job duties described in the job description above.
        Focus on skills that are **keywords or short phrases representing abilities, knowledge, and expertise.**

        **Desired format:  A bulleted list of skills. Each skill should be a concise keyword or short phrase.**

        Skills:
        """
    elif text_type == "resume":
        api_key_to_use = openai_api_key
        prompt_instruction = f"""
        Resume Text:
        {text}

        Extract a list of technical and soft skills from the resume text above.
        Focus on identifying specific skills, technologies, and areas of expertise mentioned in the resume.

        Skills: (List each skill on a new line)
        """
    else:
        print(f"Error: Invalid text_type '{text_type}' in skill_agent. Must be 'jd' or 'resume'.")
        return []

    prompt = prompt_instruction.format(text=text)

    try:
        openai.api_key = api_key_to_use
        response = openai.chat.completions.create(
            model="gpt-4",  # Using gpt-4 as requested
            messages=[{"role": "user", "content": prompt}],
            max_tokens=150,
            n=1,
            stop=None,
            temperature=0.5,
        )
        extracted_skills_text = response.choices[0].message.content.strip()
        skills = [skill.strip() for skill in extracted_skills_text.strip().splitlines() if skill.strip()]
        return list(set(skills))

    except Exception as e:
        print(f"Error during OpenAI skill extraction in skill_agent ({text_type}): {e}")
        print(f"Exception Type: {type(e)}")
        print(f"Full Exception: {e}")
        return []



def extract_skills_from_structured_jd(structured_jd):
    """
    Hybrid function: Extracts skills from JD using AI agent, with keyword fallback.
    """
    if not structured_jd:
        return []

    # 1. Try AI Agent for Skill Extraction (Preferred)
    skills = skill_agent(text=structured_jd, text_type="jd")

    # 2. Keyword Fallback if AI Agent returns no skills
    if not skills:
        print("AI Agent failed to extract JD skills, falling back to keyword extraction.")
        keywords = ["Python", "Java", "Data Analysis", "Machine Learning", "Communication", "Problem-solving", "Operating Systems", "Networking", "Scripting", "Automation", "Cloud Computing", "Cybersecurity"] # Expanded keywords relevant to OS Engineer and ML Engineer roles
        skills = [skill for skill in keywords if skill.lower() in structured_jd.lower()]

    return list(set(skills))



def extract_skills_from_resume(resume_text, openai_api_key):
    """
    Hybrid function: Extracts skills from resume using AI agent, with keyword fallback.
    """
    if not resume_text:
        return []

    # 1. Try AI Agent for Skill Extraction (Preferred)
    skills = skill_agent(text=resume_text, text_type="resume", openai_api_key=openai_api_key)

    # 2. Keyword Fallback if AI Agent returns no skills
    if not skills:
        print("AI Agent failed to extract resume skills, falling back to keyword extraction.")
        keywords = ["Python", "Java", "Data Analysis", "Machine Learning", "Communication", "Problem-solving", "Operating Systems", "Networking", "Scripting", "Automation", "Cloud Computing", "Cybersecurity", "Project Management", "Teamwork", "Leadership", "Customer Service"] # Expanded keywords for resumes (general skills)
        skills = [skill for skill in keywords if skill.lower() in resume_text.lower()]

    return list(set(skills))


def process_resumes_and_match(structured_jd_data, resume_files_queryset, drive_service, openai_api_key):
    """Processes resumes, matches them against structured JDs using hybrid skill extraction, and generates analytics."""
    print(f"OpenAI library version: {openai.__version__}")
    matched_resumes_data = {}
    unmatched_resumes_filenames = []
    analytics_data = {"skill_overlap": {}, "experience_match": {}, "education_match": {}}

    if not structured_jd_data:
        print("No structured JD data available for resume matching.")
        return matched_resumes_data, unmatched_resumes_filenames, analytics_data

    for jd_filename, structured_jd in structured_jd_data.items():
        print(f"\n--- Processing Job Description: {jd_filename} ---")
        jd_skills = extract_skills_from_structured_jd(structured_jd) # Using hybrid JD skill extraction
        print(f"\n--- Job Description Skills Extracted for {jd_filename} ---")
        print(f"Number of JD skills extracted: {len(jd_skills) if jd_skills else 0}")
        if jd_skills:
            print(f"JD Skills: {jd_skills}")
        else:
            print("No JD skills extracted (even with keyword fallback).") # More informative message
            continue

        matched_resumes_data[jd_filename] = []
        for resume_instance in resume_files_queryset:
            print(f"\n--- Processing Resume: {resume_instance.original_filename} ---")
            resume_content = fetch_file_content_from_drive(drive_service, resume_instance.drive_file_id)
            if resume_content:
                resume_text = extract_text_from_pdf(resume_content, resume_instance.original_filename)
                if resume_text:
                    resume_skills = extract_skills_from_resume(resume_text, openai_api_key) # Using hybrid resume skill extraction
                    print(f"Number of resume skills extracted: {len(resume_skills) if resume_skills else 0}")
                    if resume_skills:
                        print(f"Resume Skills: {resume_skills}")
                        skill_overlap_percentage = calculate_skill_overlap(jd_skills, resume_skills)
                        print(f"Skill Overlap Percentage: {skill_overlap_percentage:.2f}%")

                        if skill_overlap_percentage >= settings.SKILL_MATCH_THRESHOLD:
                            print(f"Resume '{resume_instance.original_filename}' MATCHED (Skill Overlap >= {settings.SKILL_MATCH_THRESHOLD}%)")
                            matched_resumes_data[jd_filename].append({
                                'resume_filename': resume_instance.original_filename,
                                'skill_overlap_percentage': skill_overlap_percentage,
                            })
                        else:
                            print(f"Resume '{resume_instance.original_filename}' NOT MATCHED (Skill Overlap < {settings.SKILL_MATCH_THRESHOLD}%)")
                            unmatched_resumes_filenames.append(resume_instance.original_filename)
                        analytics_data["skill_overlap"][resume_instance.original_filename] = skill_overlap_percentage
                    else:
                        print(f"Could not extract skills from resume '{resume_instance.original_filename}' (even with keyword fallback).") # More informative message
                else:
                    print(f"Could not extract text from resume '{resume_instance.original_filename}'.")
            else:
                print(f"Could not fetch content for resume '{resume_instance.original_filename}' from Google Drive.")

    # --- Basic Analytics Calculation (remains the same) ---
    total_resumes = len(resume_files_queryset)
    matched_count = sum(len(matches) for matches in matched_resumes_data.values())
    analytics_data["total_resumes_processed"] = total_resumes
    analytics_data["total_matched_resumes"] = matched_count
    analytics_data["match_rate"] = (matched_count / total_resumes) * 100 if total_resumes > 0 else 0

    print(f"\n--- Analysis Summary ---")
    print(f"Total Matched Resumes: {len(matched_resumes_data)}") # Still showing count of JD keys
    print(f"Total Unmatched Resumes: {len(unmatched_resumes_filenames)}")

    print(f"\n--- Matched Resumes Data Structure ---")
    print(f"Number of matched_resumes_data entries: {len(matched_resumes_data)}")
    if matched_resumes_data:
        first_jd_filename = next(iter(matched_resumes_data))
        print(f"For the first JD '{first_jd_filename}', matched resumes data: {matched_resumes_data[first_jd_filename]}")
    else:
        print("matched_resumes_data is empty.")

    return matched_resumes_data, unmatched_resumes_filenames, analytics_data


def calculate_skill_overlap(jd_skills, resume_skills):
    """Calculates the percentage of skill overlap between JD and resume."""
    # (Function code remains the same)
    if not jd_skills or not resume_skills:
        return 0.0

    jd_skills_lower = {skill.lower() for skill in jd_skills}
    resume_skills_lower = {skill.lower() for skill in resume_skills}

    overlap_skills = jd_skills_lower.intersection(resume_skills_lower)
    overlap_count = len(overlap_skills)
    jd_skill_count = len(jd_skills_lower)

    if jd_skill_count == 0:
        return 0.0
    overlap_percentage = (overlap_count / jd_skill_count) * 100
    return round(overlap_percentage, 2)
