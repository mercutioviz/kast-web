# ZAP Form Validation Fix for Standard Users

## Issue Description

Standard users were encountering a form validation error when attempting to run scans:
```
zap_plan_id: Not a valid choice.
```

This occurred even though:
1. Standard users cannot select ZAP plans (the field is hidden in the UI)
2. Standard users are not allowed to run active scans (ZAP is an active plugin)
3. The field should be optional and ignored for standard users

## Root Cause

The `zap_plan_id` and `zap_config_id` form fields in `app/forms.py` were:
1. Defined as required SelectFields without the `Optional()` validator
2. Present in the HTML form but hidden from standard users via template conditionals
3. Validated by WTForms on form submission even when hidden

When browsers submitted the form:
- Hidden fields could submit empty strings, None, or cached values
- The `coerce=int` parameter would fail to convert these values
- Values that didn't match the choices list would fail validation
- Standard users would see the "Not a valid choice" error

## Solution Implemented

### 1. Added Optional Validators (`app/forms.py`)

```python
zap_plan_id = SelectField(
    'ZAP Automation Plan',
    coerce=int,
    validators=[Optional()],  # Added this
    choices=[],
    render_kw={
        'class': 'form-select',
        'data-plugin': 'zap'
    }
)

zap_config_id = SelectField(
    'ZAP Execution Configuration',
    coerce=int,
    validators=[Optional()],  # Added this
    choices=[],
    render_kw={
        'class': 'form-select',
        'data-plugin': 'zap'
    }
)
```

### 2. Added Explicit Default Values (`app/routes/main.py`)

For standard users, explicitly set field values to 0 (use default):

```python
# For zap_plan_id (standard users)
form.zap_plan_id.choices = [(0, 'Use Default ZAP Plan')]
form.zap_plan_id.data = 0  # Explicitly set

# For zap_config_id (all users)
if not default_zap_config:
    form.zap_config_id.data = 0  # Explicitly set if no default exists
```

### 3. Added Error Handling in Form Processing (`app/routes/main.py`)

Added try-except blocks to gracefully handle invalid values:

```python
try:
    if form.zap_plan_id.data and form.zap_plan_id.data != 0:
        zap_plan_id = form.zap_plan_id.data
        # ... validation logic
except (ValueError, TypeError):
    current_app.logger.warning(f"Invalid zap_plan_id value: {form.zap_plan_id.data}")
    zap_plan_id = None
```

### 4. Enforced Standard User Restrictions

Ensured standard users always use default ZAP configuration:

```python
if current_user.is_power_user or current_user.is_admin:
    # Process zap_plan_id
else:
    # Standard users cannot select ZAP plans, always use default
    zap_plan_id = None
```

## Files Modified

1. `app/forms.py` - Added `Optional()` validator to ZAP fields
2. `app/routes/main.py` - Added default values and error handling

## Testing

To verify the fix works:

1. **As a standard user:**
   - Navigate to the home page
   - Configure a passive scan (do not select ZAP)
   - Submit the form - should work without errors
   - The ZAP configuration section should remain hidden

2. **As a power user:**
   - Navigate to the home page
   - Select the ZAP plugin
   - Choose a ZAP plan and configuration
   - Submit the form - should work correctly

3. **As an admin:**
   - Test both scenarios above
   - Verify all ZAP options are available and functional

## Prevention

To prevent similar issues in the future:

1. **Always use `Optional()` validator** for fields that:
   - May be hidden from certain user roles
   - Are conditionally displayed based on other selections
   - Are not always required

2. **Explicitly set default values** for hidden or optional fields to prevent browsers from submitting unexpected values

3. **Add try-except blocks** when processing form data that may be invalid due to client-side manipulation or browser behavior

4. **Test with all user roles** to ensure form validation works correctly for each permission level

## Related Documentation

- `docs/ZAP_INTEGRATION_PHASE1.md` - ZAP integration overview
- `docs/AUTHORIZATION_PHASE2.md` - User roles and permissions
- `docs/POWER_USER_FEATURE.md` - Power user role details
- `.clinerules` - Project-specific form validation patterns