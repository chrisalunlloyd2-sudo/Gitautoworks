import os
import sys
from utils import initialize_repository, manage_commits, track_issues

def main():
    # Initialize repository
    """Main (function)."""
    initialize_repository()

    # Manage commits
    manage_commits()

    # Track issues
    track_issues()

if __name__ == "__main__":
    main()
