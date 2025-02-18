# models.py
from django.db import models

class JD(models.Model):
    original_filename = models.CharField(max_length=255, unique=True) # Filename, unique constraint
    drive_file_id = models.CharField(max_length=255) # Google Drive File ID
    drive_folder_id = models.CharField(max_length=255) # Google Drive Folder ID (optional, could be from settings)

    def __str__(self):
        return self.original_filename

class Resume(models.Model):
    original_filename = models.CharField(max_length=255, unique=True) # Filename, unique constraint
    drive_file_id = models.CharField(max_length=255) # Google Drive File ID
    drive_folder_id = models.CharField(max_length=255) # Google Drive Folder ID (optional, could be from settings)

    def __str__(self):
        return self.original_filename

class Results(models.Model):
    matched_resumes = models.JSONField(null=True, blank=True)
    unmatched_resumes = models.JSONField(null=True, blank=True)
    analytics = models.JSONField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"Results - ID: {self.id} - Created: {self.created_at.strftime('%Y-%m-%d %H:%M:%S')}"