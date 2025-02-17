# views.py
import os
import json
from django.shortcuts import render, redirect
from django.conf import settings
from django.contrib import messages
from . import utils  # Import your utils.py file
from .models import JD, Resume, Results  # Import your models


def get_api_key(request):
    """View to handle OpenAI API key input and saving to session."""
    if request.method == 'POST':
        openai_api_key = request.POST.get('openai_api_key')
        if openai_api_key:
            request.session['openai_api_key'] = openai_api_key  # Try to save to session

            # --- DEBUG SESSION SAVING ---
            test_value = "session_test_value"
            request.session['test_session_key'] = test_value # Set a test session variable
            session_saved = request.session.get('test_session_key') # Try to retrieve it immediately
            print(f"DEBUG: Session test_session_key SAVED: {session_saved == test_value}") # Print True/False if saved correctly
            print(f"DEBUG: OpenAI API key saved to session: {openai_api_key}")
            messages.success(request, 'OpenAI API key saved successfully! (Stored in session)')
            return redirect('manage_files') # Redirect to file management page after API key is set
        else:
            messages.error(request, 'Please enter an API key.')
    return render(request, 'app/get_api_key.html')


def manage_files(request):
    """View for managing job descriptions and resumes, and triggering analysis."""
    openai_api_key = request.session.get('openai_api_key') # Get API key from session
    if not openai_api_key:
        return redirect('get_api_key') # Redirect to API key input page if not in session

    drive_service = utils.get_drive_service() # Initialize Google Drive service here for efficiency

    if not drive_service: # Check if service initialization failed
        messages.error(request, "Failed to initialize Google Drive service. Check your credentials and settings.")
        # Consider redirecting to API key page or error page if Drive service is essential
        # For now, we'll proceed to render the page, but upload/delete functions might not work

    jds = JD.objects.all() # Fetch all Job Descriptions from database
    resumes = Resume.objects.all() # Fetch all Resumes from database

    if request.method == 'POST':
        print("DEBUG: request.method is: POST (inside POST block)") # VERIFY POST BLOCK ENTRY

        if 'add_jd' in request.POST and request.FILES.get('jd_file'): # Use 'add_jd' button name (from older version)
            print("DEBUG: add_jd button clicked condition is TRUE") # DEBUG
            jd_file = request.FILES.get('jd_file')
            print(f"DEBUG: jd_file received: {jd_file}") # DEBUG
            if jd_file and jd_file.name.endswith('.pdf'):
                print("DEBUG: JD file is valid PDF and file object exists") # DEBUG
                try:
                    drive_folder_id = settings.GOOGLE_DRIVE_JD_FOLDER_ID # Get JD folder ID from settings
                    print(f"DEBUG: GOOGLE_DRIVE_JD_FOLDER_ID: {drive_folder_id}") # DEBUG
                    file_id = utils.upload_to_drive(drive_service, jd_file, drive_folder_id) # Upload to Drive
                    print(f"DEBUG: utils.upload_to_drive returned file_id: {file_id}") # DEBUG
                    if file_id:
                        JD.objects.create(original_filename=jd_file.name, drive_file_id=file_id, drive_folder_id=drive_folder_id) # Save JD info to DB
                        messages.success(request, f'Job Description "{jd_file.name}" uploaded successfully.')
                        print(f"DEBUG: JD record created in database for '{jd_file.name}'") # DEBUG
                    else:
                        messages.error(request, f'Error uploading Job Description "{jd_file.name}" to Google Drive.')
                        print(f"DEBUG: upload_to_drive failed for JD '{jd_file.name}' - file_id is None") # DEBUG
                except Exception as e:
                    messages.error(request, f'File upload error for JD "{jd_file.name}": {e}')
                    print(f"DEBUG: Exception during JD upload: {e}") # DEBUG
            else:
                messages.error(request, 'Invalid file format. Please upload a PDF file for Job Description.')
                if not jd_file:
                    print("DEBUG: JD file object is None (no file selected?)") # DEBUG
                elif jd_file:
                    print(f"DEBUG: JD file is not a PDF. Filename: '{jd_file.name}'") # DEBUG

        elif 'add_resumes' in request.POST and request.FILES.getlist('resume_files'): # Use 'add_resumes' button name (from older version)
            print("DEBUG: add_resumes button clicked condition is TRUE") # DEBUG
            resume_files = request.FILES.getlist('resume_files') # Use getlist to handle multiple files
            print(f"DEBUG: resume_files received: {resume_files}") # DEBUG

            if resume_files:
                print("DEBUG: Resume files list is not empty") # DEBUG
                try:
                    drive_folder_id = settings.GOOGLE_DRIVE_RESUME_FOLDER_ID # Get Resume folder ID from settings
                    print(f"DEBUG: GOOGLE_DRIVE_RESUME_FOLDER_ID: {drive_folder_id}") # DEBUG
                    uploaded_count = 0
                    for resume_file in resume_files:
                        print(f"DEBUG: Processing resume file: {resume_file.name}") # DEBUG
                        if resume_file.name.endswith('.pdf'):
                            print("DEBUG: Resume file is a PDF") # DEBUG
                            file_id = utils.upload_to_drive(drive_service, resume_file, drive_folder_id) # Upload each resume
                            print(f"DEBUG: utils.upload_to_drive for resume '{resume_file.name}' returned file_id: {file_id}") # DEBUG
                            if file_id:
                                Resume.objects.create(original_filename=resume_file.name, drive_file_id=file_id, drive_folder_id=drive_folder_id) # Save Resume info to DB
                                uploaded_count += 1
                                print(f"DEBUG: Resume record created in database for '{resume_file.name}'") # DEBUG
                            else:
                                messages.error(request, f'Error uploading resume "{resume_file.name}" to Google Drive.') # Individual resume upload error
                                print(f"DEBUG: upload_to_drive failed for resume '{resume_file.name}' - file_id is None") # DEBUG
                        else:
                             messages.error(request, f'Invalid file format for resume "{resume_file.name}". Please upload PDF files only.') # Individual resume format error
                             print(f"DEBUG: Resume file '{resume_file.name}' is not a PDF") # DEBUG

                    if uploaded_count > 0:
                        messages.success(request, f'{uploaded_count} resumes uploaded successfully.')
                        print(f"DEBUG: {uploaded_count} resumes uploaded successfully (overall)") # DEBUG
                except Exception as e:
                    messages.error(request, f'Error uploading resumes: {e}')
                    print(f"DEBUG: Exception during resume upload: {e}") # DEBUG
            else:
                print("DEBUG: resume_files list is empty (no files selected?)") # DEBUG

        elif 'delete_jd' in request.POST: # Use 'delete_jd' button name (from older version)
            jd_id = request.POST.get('jd_to_delete')
            try:
                jd_to_delete = JD.objects.get(pk=jd_id) # Get JD object from DB
                if utils.delete_file_from_drive(drive_service, jd_to_delete.drive_file_id): # Delete from Drive
                    jd_to_delete.delete() # Delete JD record from DB
                    messages.success(request, f'Job Description "{jd_to_delete.original_filename}" deleted successfully.') # Use jd_to_delete.original_filename
                else:
                    messages.error(request, f'Error deleting Job Description "{jd_to_delete.original_filename}" from Google Drive.') # Use jd_to_delete.original_filename
            except JD.DoesNotExist:
                messages.error(request, f'Job Description with id "{jd_id}" not found in database.') # Use jd_id in message
            except Exception as e:
                messages.error(request, f'Error deleting Job Description with id "{jd_id}": {e}') # Use jd_id in message

        elif 'delete_resume' in request.POST: # Use 'delete_resume' button name (from older version)
            resume_id = request.POST.get('resume_to_delete')
            try:
                resume_to_delete = Resume.objects.get(pk=resume_id) # Get Resume object
                if utils.delete_file_from_drive(drive_service, resume_to_delete.drive_file_id): # Delete from Drive
                    resume_to_delete.delete() # Delete Resume record
                    messages.success(request, f'Resume "{resume_to_delete.original_filename}" deleted successfully.') # Use resume_to_delete.original_filename
                else:
                    messages.error(request, f'Error deleting Resume "{resume_to_delete.original_filename}" from Google Drive.') # Use resume_to_delete.original_filename
            except Resume.DoesNotExist:
                messages.error(request, f'Resume with id "{resume_id}" not found in database.') # Use resume_id in message
            except Exception as e:
                messages.error(request, f'Error deleting Resume with id "{resume_id}": {e}') # Use resume_id in message


        elif 'process_files' in request.POST: # Keep 'process_files' button name (consistent)
            openai_api_key = request.session.get('openai_api_key') # Get API key from session
            if not openai_api_key:
                messages.error(request, "OpenAI API key is not set in session. Please enter it on the API Key page.")
                return redirect('get_api_key') # Redirect to API key input page

            jd_files_queryset = JD.objects.all() # Get all JDs for processing
            resume_files_queryset = Resume.objects.all() # Get all Resumes for processing

            if not jd_files_queryset or not resume_files_queryset: # Check if any files are uploaded
                messages.warning(request, "Please upload at least one Job Description and one Resume to process.")
            else:
                try:
                    structured_jd_data = {} # Dictionary to store structured JD data
                    for jd_instance in jd_files_queryset:
                        jd_content = utils.fetch_file_content_from_drive(drive_service, jd_instance.drive_file_id) # Fetch JD content
                        if jd_content:
                            jd_text = utils.extract_text_from_pdf(jd_content, jd_instance.original_filename) # Extract text from JD
                            if jd_text:
                                structured_jd = utils.clean_and_structure_jd(jd_text, openai_api_key) # Structure JD using OpenAI
                                structured_jd_data[jd_instance.original_filename] = structured_jd # Store structured JD data
                            else:
                                messages.error(request, f'Could not extract text from Job Description "{jd_instance.original_filename}".')
                                return render(request, 'app/manage_files.html', {'jds': jds, 'resumes': resumes}) # Render page with error

                        else:
                            messages.error(request, f'Could not fetch content for Job Description "{jd_instance.original_filename}" from Google Drive.')
                            return render(request, 'app/manage_files.html', {'jds': jds, 'resumes': resumes}) # Render page with error

                    # --- Resume Processing and Matching ---
                    matched_resumes_data, unmatched_resumes_filenames, analytics_data = utils.process_resumes_and_match(
                        structured_jd_data, resume_files_queryset, drive_service, openai_api_key
                    ) # Process resumes and match

                    # --- Visualization (Placeholder - replace with actual visualization if needed) ---
                    plot_filename = utils.visualize_analytics(analytics_data) # Generate analytics plot (placeholder for now)
                    plot_url = None # Initialize plot_url to None
                    if plot_filename:
                        plot_url = os.path.join(settings.MEDIA_URL, plot_filename) # Construct media URL for plot

                    # --- Save Results to Database ---
                    results_instance = Results.objects.create(
                        matched_resumes=matched_resumes_data,
                        unmatched_resumes=unmatched_resumes_filenames,
                        analytics=analytics_data # Save analytics as dictionary
                    )

                    messages.success(request, 'Resume analysis completed and results saved.')
                    return redirect('analysis_results', results_id=results_instance.id) # Redirect to results page

                except Exception as e:
                    messages.error(request, f'Error during resume processing and analysis: {e}')

    context = {
        'jds': jds,
        'resumes': resumes,
    }
    return render(request, 'app/manage_files.html', context)

def analysis_results(request, results_id):
    """View to display analysis results, including analytics and matched resumes by role."""
    results = Results.objects.get(pk=results_id) # Fetch Results object from DB
    matched_resumes_data = results.matched_resumes # Retrieve matched resumes data (already a Python dict from JSONField)
    unmatched_resumes_filenames = results.unmatched_resumes # Retrieve unmatched resume filenames
    analytics_data = results.analytics # Retrieve analytics data (already a Python dict from JSONField)

    # Prepare analytics data for display (convert counts to integers if needed, ensure data structure is as expected)
    analytics_display_data = analytics_data # For now, assuming analytics data is ready for display

    # Get plot URL from utils (if plot was generated and filename saved)
    plot_filename = utils.visualize_analytics(analytics_display_data) # Re-generate plot for display (or fetch saved plot info if you save plot path in Results model)
    plot_url = None # Initialize plot_url to None
    if plot_filename:
        plot_url = os.path.join(settings.MEDIA_URL, plot_filename) # Construct media URL

    context = {
        'results': results,
        'matched_resumes': matched_resumes_data, # Pass matched resumes data directly
        'unmatched_resumes': unmatched_resumes_filenames,
        'analytics_display_data': analytics_display_data, # Pass analytics data for display
        'plot_url': plot_url, # URL for the analytics plot image
    }
    return render(request, 'app/analysis_results.html', context)


def display_top_resumes(request, results_id):
    """View to display top matched resumes for a specific job role."""
    results = Results.objects.get(pk=results_id) # Fetch Results object
    matched_resumes_data = results.matched_resumes # Get matched resumes data
    selected_role = request.GET.get('role') # Get selected role from query parameters

    matched_resumes_for_role = []
    if selected_role and matched_resumes_data and selected_role in matched_resumes_data:
        matched_resumes_for_role = matched_resumes_data[selected_role] # Get matches for the selected role

    context = {
        'results_id': results_id, # Pass results_id for back link
        'selected_role': selected_role,
        'matched_resumes_for_role': matched_resumes_for_role,
    }
    return render(request, 'app/top_resumes.html', context)