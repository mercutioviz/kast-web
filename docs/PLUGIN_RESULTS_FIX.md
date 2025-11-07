# Plugin Results Display Fixes

## Issues Fixed

### 1. Incorrect Findings Count
**Problem**: All plugins were showing 4 findings because the code was counting the top-level `findings` array which always has 4 items (metadata). The actual results are in `findings['results']`.

**Solution**: Updated `app/tasks.py` in the `parse_scan_results()` function to correctly count findings:
- Check if `findings` is a dictionary and extract the `results` array
- Count the length of `findings['results']` instead of `findings`
- Added fallback logic for different data structures

### 2. Executed Time Not Updating During Scan
**Problem**: The "Executed" column showed "N/A" for all plugins during the scan and only updated when the entire scan completed.

**Solution**: 
1. **In `app/tasks.py`**: Modified `parse_scan_results()` to use the file modification time of the `_processed.json` file as the `executed_at` timestamp. This provides an accurate timestamp of when each plugin completed.

2. **In `app/routes/api.py`**: Added a call to `parse_scan_results()` during the status polling when a scan is running. This ensures that as each plugin completes and creates its `_processed.json` file, the database is immediately updated with the findings count and execution time.

## Files Modified

1. **app/tasks.py**
   - Updated findings counting logic to look at `findings['results']`
   - Changed `executed_at` to use file modification time instead of current time
   - Added proper handling for different findings data structures
   - Modified to update existing records instead of creating duplicates

2. **app/routes/api.py**
   - Added real-time parsing of results during scan execution
   - Ensures database is updated as each plugin completes

3. **app/utils.py**
   - Fixed `parse_scan_results()` function to use correct findings counting logic
   - Changed to update existing records instead of always creating new ones
   - This was the critical fix that prevented findings from resetting to 4 when scan completed

## How It Works Now

1. When a plugin completes and creates its `_processed.json` file, the file's modification time is recorded
2. During status polling (every 3 seconds), the API endpoint calls `parse_scan_results()`
3. This function reads any new `_processed.json` files and:
   - Counts the actual findings from `findings['results']`
   - Records the file modification time as `executed_at`
   - Updates or creates the database record
4. The frontend receives the updated data and displays:
   - Correct findings count
   - Execution time for each completed plugin

## Testing

To verify the fixes:
1. Start a new scan with multiple plugins
2. Watch the scan detail page as it runs
3. Verify that:
   - Each plugin shows its execution time as it completes (not "N/A")
   - The findings count reflects the actual number of results, not always 4
   - Times update in real-time during the scan, not just at the end
