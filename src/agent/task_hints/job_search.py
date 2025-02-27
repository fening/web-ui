
JOB_SEARCH_HINTS = """
# Job Search Best Practices

When searching for jobs in specific locations:

1. IMPORTANT: Always use the location filter feature of the job platform first
   - Use the new `filter_jobs_by_location` action to automatically set location filters
   - Example: `{"action_type": "filter_jobs_by_location", "location": "Houston, TX", "platform": "linkedin"}`

2. For form input fields:
   - Use the `smart_form_fill` action instead of regular input_text when working with forms
   - Example: `{"action_type": "smart_form_fill", "selector": "Phone Number", "text": "5551234567"}`

3. Check if a job is remote or located in your target city BEFORE applying

4. Common issues and solutions:
   - If trying to input text into a label element, use `smart_form_fill` instead
   - If location filters aren't working, try manually entering the location in the search field
   - If applying to a job, make sure all required fields are filled before submitting

5. For LinkedIn specifically:
   - Look for the "Jobs" tab first
   - Use the location filter consistently
   - Check each job's location in the job details pane
"""
