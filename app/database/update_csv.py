import csv
import os

def update_pitchers_csv():
    """Update the pitchers CSV file to include BABIP and FIP columns."""
    csv_path = os.path.join(os.path.dirname(__file__), 'players-pitchers.csv')
    temp_path = os.path.join(os.path.dirname(__file__), 'players-pitchers-temp.csv')
    
    # Read the existing CSV
    with open(csv_path, 'r', encoding='utf-8') as f:
        reader = csv.DictReader(f)
        fieldnames = reader.fieldnames
        
        # Check if the columns already exist
        if 'BABIP' in fieldnames and 'FIP' in fieldnames:
            print("CSV already has BABIP and FIP columns.")
            return
        
        # Add the new columns
        fieldnames = fieldnames + ['BABIP', 'FIP']
        
        # Write to a temporary file
        with open(temp_path, 'w', encoding='utf-8', newline='') as temp_file:
            writer = csv.DictWriter(temp_file, fieldnames=fieldnames)
            writer.writeheader()
            
            # Copy the existing data and add empty values for new columns
            for row in reader:
                row['BABIP'] = ''
                row['FIP'] = ''
                writer.writerow(row)
    
    # Replace the original file with the updated one
    os.replace(temp_path, csv_path)
    print("CSV updated successfully with BABIP and FIP columns.")

if __name__ == "__main__":
    update_pitchers_csv() 