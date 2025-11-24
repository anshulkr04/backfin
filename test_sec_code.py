"""Quick test to verify sec_code string handling"""
import pandas as pd

# Simulate BSE CSV data with numeric sec_code
test_data = pd.DataFrame({
    'sec_code': [500325, 532540.0, '500180', None, '  500696  '],
    'sec_name': ['Company A', 'Company B', 'Company C', 'Company D', 'Company E'],
    'person_name': ['John Doe', 'Jane Smith', 'Bob Wilson', 'Alice Brown', 'Charlie Davis']
})

print("Original data:")
print(test_data)
print("\nData types:")
print(test_data.dtypes)

# Apply the sec_code string processing logic (improved version)
def clean_sec_code(x):
    if x is None or pd.isna(x):
        return None
    s = str(x).strip()
    if s in ('', 'nan', 'None'):
        return None
    # Remove decimal point for integer values (e.g., '532540.0' -> '532540')
    if '.' in s:
        try:
            float_val = float(s)
            if float_val == int(float_val):  # Check if it's a whole number
                s = str(int(float_val))
        except (ValueError, OverflowError):
            pass
    return s

filtered = test_data.copy()
filtered['sec_code'] = filtered['sec_code'].apply(clean_sec_code)

print("\nAfter string processing:")
print(filtered)
print("\nData types:")
print(filtered.dtypes)

print("\nVerification:")
for idx, row in filtered.iterrows():
    sec_code = row['sec_code']
    print(f"Row {idx}: sec_code='{sec_code}' type={type(sec_code).__name__} is_string={isinstance(sec_code, str) or sec_code is None}")
