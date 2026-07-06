"""Functions for db maintenance."""

import sqlite3

from esi_link.app_data.helpers import transaction


# Functions for things like vacuuming the database, etc. Not for general use, but for maintenance tasks.
# - reporting stats
# - vacuuming
# - droping old cache entries
# - dropping tables - usually for dev purposes.
#
def example(connection: sqlite3.Connection):
    """Example function for db maintenance."""
    # Vacuum the database to reclaim space and optimize performance.
    with transaction(connection) as conn:
        conn.execute("VACUUM")
