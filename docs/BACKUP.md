# Backup and restore

The backup is ONE JSON file holding every table: stock, sales, purchases, customers, settings, and **your password hash**. Keep it private.

## Make a backup
* **In the app:** Settings -> Download backup. File name `azeem-backup-DATE.json`.
* **From Windows, any database** (also works against Supabase):

      cd backend
      venv\Scripts\activate
      set DATABASE_URL=your-database-url
      python -m app.cli backup my-backup.json

**Do this weekly** and keep copies away from the PC (USB, your own cloud drive). Free Supabase has no automatic backups.

## Restore
* **In the app:** Settings -> Restore backup. Choose the file, type your password, confirm. **Everything currently in the system is replaced.**
  It is all-or-nothing: if the file is damaged, nothing changes.
* **Command line:** `python -m app.cli restore my-backup.json` (asks you to type RESTORE).

## Good to know
* A backup restores the old owner password too.
* A backup can only be restored by the same database version (the file records it). After upgrading the app, make a fresh backup.
* Test your backups: restore into a throw-away local copy with `set DATABASE_URL=sqlite:///test.db` then `python -m app.cli restore my-backup.json`.
* Moving from your PC to the cloud: back up locally, point `DATABASE_URL` at Supabase, restore.
