"""
Company Database Management System

This package provides a verification workflow for managing changes to the stocklistdata table.
All new companies and changes to existing companies must be verified before being applied.

Modules:
    detect_changes: Detects and submits company changes for verification
    
Workflow:
    1. Detect changes from exchange data
    2. Submit to company_changes_pending table
    3. Admin/verifier reviews and approves changes
    4. Admin applies verified changes to stocklistdata
"""

__version__ = "1.0.0"
__all__ = ["detect_changes"]
