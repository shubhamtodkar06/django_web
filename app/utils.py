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


def upload_to_drive(service, uploaded_file, drive_folder_id):
    """
    Uploads a file to Google Drive, handling temporary file creation and cleanup,
    with retry logic for deletion on failure. Includes detailed debug prints and cleaner temp file handling.
    """
    if service is None:
        print("Google Drive service not initialized. Cannot upload file.")
        return None

    try:
        file_metadata = {'name': uploaded_file.name, 'parents': [drive_folder_id]}
        temp_file_path = None

        try: # Inner try block for file operations and Drive upload
            print(f"UPLOAD START: Creating temp file for {uploaded_file.name}...")
            with tempfile.NamedTemporaryFile(delete=False, suffix=".tmp") as temp_file: # Cleaner temp file handling
                temp_file_path = temp_file.name
                print(f"UPLOAD PROGRESS: Temp file created at {temp_file_path}")

                print(f"UPLOAD PROGRESS: Writing content to temp file {temp_file_path}...")
                for chunk in uploaded_file.chunks():
                    temp_file.write(chunk)
                print(f"UPLOAD PROGRESS: Content written to temp file.")
            # temp_file is automatically closed here when exiting 'with' block

            print(f"UPLOAD PROGRESS: Starting Google Drive upload from {temp_file_path}...")
            media = MediaFileUpload(temp_file_path, mimetype=uploaded_file.content_type)
            print(f"UPLOAD PROGRESS: MediaFileUpload object created.")
            file = service.files().create(body=file_metadata, media_body=media, fields='id').execute()
            print(f"UPLOAD PROGRESS: Drive API 'files().create' request executed.")
            drive_file_id = file.get('id')
            print(f"UPLOAD SUCCESS: File ID: {drive_file_id} for {uploaded_file.name}")
            return drive_file_id

        finally:  # Cleanup block - Executes whether upload succeeds or fails
            if temp_file_path:
                print(f"CLEANUP START: Attempting to remove temp file {temp_file_path} for {uploaded_file.name}...")
                max_retries = 5
                retry_delay = 2
                for retry_attempt in range(max_retries):
                    try:
                        time.sleep(retry_delay)
                        os.remove(temp_file_path)
                        print(f"CLEANUP SUCCESS: Temp file {temp_file_path} removed after {retry_attempt+1} attempt(s) for {uploaded_file.name}")
                        break
                    except Exception as e_delete:
                        if retry_attempt < max_retries - 1:
                            print(f"CLEANUP RETRY {retry_attempt+2}/{max_retries}: Error removing temp file {temp_file_path} for {uploaded_file.name}: {e_delete}. Retrying in {retry_delay} seconds...")
                            time.sleep(retry_delay)
                        else:
                            print(f"CLEANUP ERROR: Final attempt failed to remove temp file {temp_file_path} for {uploaded_file.name} after {max_retries} retries: {e_delete}")
                            break
                else:
                    pass # Deletion was successful in one of the retries


    except Exception as e: # Outer try block - general upload errors
        print(f"UPLOAD ERROR: General error during Drive upload for {uploaded_file.name}: {e}")
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


def process_resumes_and_match(structured_jd_data, resume_files_queryset, drive_service, openai_api_key):
    """Processes resumes, matches them against structured JDs, and generates analytics."""
    matched_resumes_data = {}
    unmatched_resumes_filenames = []
    analytics_data = {"skill_overlap": {}, "experience_match": {}, "education_match": {}} # Analytics data dictionary

    if not structured_jd_data:
        print("No structured JD data available for resume matching.")
        return matched_resumes_data, unmatched_resumes_filenames, analytics_data

    for jd_filename, structured_jd in structured_jd_data.items():
        # jd_skills = utils.extract_skills_from_structured_jd(structured_jd) # Example - adjust as needed - keeping this function call though it needs to be implemented
        jd_skills = extract_skills_from_structured_jd(structured_jd) # Corrected: calling the function from within utils.py
        if not jd_skills:
            print(f"Could not extract skills from structured JD for '{jd_filename}'. Skipping resume matching for this JD.")
            continue

        matched_resumes_data[jd_filename] = []
        for resume_instance in resume_files_queryset:
            resume_content = fetch_file_content_from_drive(drive_service, resume_instance.drive_file_id)
            if resume_content:
                resume_text = extract_text_from_pdf(resume_content, resume_instance.original_filename)
                if resume_text:
                    # resume_skills = utils.extract_skills_from_resume(resume_text, openai_api_key) # Example - adjust as needed - keeping this function call though it needs to be implemented
                    resume_skills = extract_skills_from_resume(resume_text, openai_api_key) # Corrected: calling the function from within utils.py
                    if resume_skills:
                        skill_overlap_percentage = calculate_skill_overlap(jd_skills, resume_skills)
                        if skill_overlap_percentage >= settings.SKILL_MATCH_THRESHOLD:
                            matched_resumes_data[jd_filename].append({
                                'resume_filename': resume_instance.original_filename,
                                'skill_overlap_percentage': skill_overlap_percentage,
                                # ... you can add more matching criteria and data here
                            })
                        else:
                            unmatched_resumes_filenames.append(resume_instance.original_filename)
                        analytics_data["skill_overlap"][resume_instance.original_filename] = skill_overlap_percentage
                    else:
                        print(f"Could not extract skills from resume '{resume_instance.original_filename}'.")
                else:
                    print(f"Could not extract text from resume '{resume_instance.original_filename}'.")
            else:
                print(f"Could not fetch content for resume '{resume_instance.original_filename}' from Google Drive.")

    # --- Basic Analytics Calculation
    total_resumes = len(resume_files_queryset)
    matched_count = sum(len(matches) for matches in matched_resumes_data.values())
    analytics_data["total_resumes_processed"] = total_resumes
    analytics_data["total_matched_resumes"] = matched_count
    analytics_data["match_rate"] = (matched_count / total_resumes) * 100 if total_resumes > 0 else 0

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

def extract_skills_from_structured_jd(structured_jd):
    """
    Example function to extract skills from a structured job description.
    Placeholder - needs actual implementation.
    """
    if not structured_jd:
        return []

    skills = []
    if "Technical Skills:" in structured_jd:
        skills_section = structured_jd.split("Technical Skills:")[1]
        skills = [skill.strip() for skill in skills_section.strip().split("\n") if skill.strip()]
    elif "Skills:" in structured_jd:
        skills_section = structured_jd.split("Skills:")[1]
        skills = [skill.strip() for skill in skills_section.strip().split("\n") if skill.strip()]

    if not skills:
        keywords = ["Python", "Java", "Data Analysis", "Machine Learning", "Communication", "Problem-solving"]
        skills = [skill for skill in keywords if skill.lower() in structured_jd.lower()]

    return list(set(skills))


def extract_skills_from_resume(resume_text, openai_api_key):
    """
    Extracts skills from resume text using OpenAI.
    """
    if not resume_text:
        print("No resume text provided for skill extraction.")
        return None

    prompt = f"Extract key skills from the following resume text:\n\n{resume_text}\n\n... Skills (comma-separated):"
    try:
        from openai import OpenAI # Import OpenAI here, only when needed
        client = OpenAI(api_key=openai_api_key)
        response = client.chat.completions.create(
            model="gpt-3.5-turbo",
            messages=[{"role": "user", "content": prompt}]
        )
        extracted_skills_text = response.choices[0].message.content
        if extracted_skills_text:
            skills_list = [skill.strip() for skill in extracted_skills_text.split(',') if skill.strip()]
            return skills_list
        else:
            print("OpenAI skill extraction returned empty content.")
            return []
    except Exception as e:
        print(f"Error during OpenAI resume skill extraction: {e}")
        return None


def calculate_skill_overlap(jd_skills, resume_skills):
    """Calculates the percentage of skill overlap between JD and resume."""
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

