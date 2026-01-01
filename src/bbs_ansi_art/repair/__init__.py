"""
Repair module - clean and fix problematic ANSI art files.

Provides tools to remove escape sequences that cause display issues
on modern terminals while preserving the visual content.
"""

from bbs_ansi_art.repair.cleaner import clean_bytes, clean_file, strip_sauce, strip_text, CleanResult

__all__ = ["clean_bytes", "clean_file", "strip_sauce", "strip_text", "CleanResult"]
